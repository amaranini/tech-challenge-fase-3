"""Wrapper de treino LoRA. Lê o YAML, mostra resumo, pede confirmação,
roda o `mlx_lm.lora` como subprocesso e captura métricas em
`finetuning/output/training_log.json`.

Características importantes:
- Imprime um banner com hiperparâmetros, tamanho do dataset e tempo
  estimado antes de começar.
- Pergunta "Prosseguir? [s/N]" — não inicia sozinho.
- É **resiliente a Ctrl+C**: envia SIGINT pro mlx-lm pra que ele salve o
  checkpoint atual antes de morrer.
- Captura linhas de `Train loss`/`Val loss` da stdout e grava
  incrementalmente em `training_log.json` (cada item bem-sucedido
  fica no disco mesmo se o processo cair).

Uso:
    uv run python finetuning/train.py              # treino completo
    uv run python finetuning/train.py --smoke-test  # 10 iters, para validar setup
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "configs" / "lora_config.yaml"
OUTPUT_DIR = HERE / "output"
LOG_PATH = OUTPUT_DIR / "training_log.json"

# Regex para parsear a stdout do mlx-lm. As linhas reais do mlx-lm têm formato:
#   Iter 10: Train loss 6.124, Learning Rate 1.000e-05, It/sec 0.123, ...
#   Iter 25: Val loss 5.234, Val took 12.5s
# Como o formato pode variar entre versões, usamos regex tolerante.
ITER_TRAIN_RE = re.compile(
    r"Iter\s+(\d+):.*?Train loss\s+([\d.]+).*?Learning Rate\s+([\d.eE+-]+)",
    re.IGNORECASE,
)
ITER_VAL_RE = re.compile(
    r"Iter\s+(\d+):.*?Val loss\s+([\d.]+)",
    re.IGNORECASE,
)


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open() as f:
        return sum(1 for line in f if line.strip())


def _print_banner(config: dict, smoke_test: bool) -> None:
    train_n = _count_jsonl_lines(HERE / "data" / "train.jsonl")
    valid_n = _count_jsonl_lines(HERE / "data" / "valid.jsonl")
    test_n = _count_jsonl_lines(HERE / "data" / "test.jsonl")

    iters = config["iters"]
    batch = config["batch_size"]
    grad_acc = config.get("grad_accumulation_steps", 1)
    effective_batch = batch * grad_acc
    # Estimativa conservadora pro M1 base 7-8 GPU cores
    sec_per_iter = 7.0
    eta_min = iters * sec_per_iter / 60

    print("=" * 64)
    print("  Fine-tuning LoRA — medical-assistant")
    if smoke_test:
        print("  ⚠ MODO SMOKE TEST (10 iters)")
    print("=" * 64)
    print(f"  Modelo base : {config['model']}")
    print(f"  Adapter out : {config['adapter_path']}")
    print(f"  Dataset     : train={train_n} | valid={valid_n} | test={test_n}")
    print(f"  Iters       : {iters} (batch efetivo {effective_batch})")
    print(f"  Learning rt : {config['learning_rate']}")
    print(f"  Seq max     : {config['max_seq_length']} tokens")
    print(f"  LoRA        : rank={config['lora_parameters']['rank']}, "
          f"scale={config['lora_parameters']['scale']}, "
          f"dropout={config['lora_parameters']['dropout']}")
    print(f"  num_layers  : {config['num_layers']}")
    print(f"  Eta         : ~{eta_min:.0f} min (estimativa conservadora)")
    print("=" * 64)


def _build_smoke_config(orig: dict) -> Path:
    """Cria um YAML temporário com iters=10 (para o smoke test)."""
    smoke = dict(orig)
    smoke["iters"] = 10
    smoke["steps_per_eval"] = 5
    smoke["save_every"] = 10
    smoke["steps_per_report"] = 2
    smoke["adapter_path"] = "finetuning/output/adapters_smoke"
    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="lora_smoke_")
    os.close(fd)
    Path(tmp_path).write_text(yaml.safe_dump(smoke, sort_keys=False), encoding="utf-8")
    return Path(tmp_path)


def _save_log(entries: list[dict]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_and_log(line: str, entries: list[dict], t0: float) -> None:
    train_m = ITER_TRAIN_RE.search(line)
    if train_m:
        entries.append({
            "type": "train",
            "iter": int(train_m.group(1)),
            "train_loss": float(train_m.group(2)),
            "lr": float(train_m.group(3)),
            "elapsed_sec": round(time.monotonic() - t0, 2),
        })
        _save_log(entries)
        return
    val_m = ITER_VAL_RE.search(line)
    if val_m:
        entries.append({
            "type": "val",
            "iter": int(val_m.group(1)),
            "val_loss": float(val_m.group(2)),
            "elapsed_sec": round(time.monotonic() - t0, 2),
        })
        _save_log(entries)


def _run_training(config_path: Path) -> tuple[int, list[dict], float]:
    """Roda mlx_lm.lora como subprocesso, parseia stdout linha a linha.
    Retorna (exit_code, log_entries, elapsed_sec)."""
    cmd = [
        sys.executable, "-m", "mlx_lm", "lora",
        "--config", str(config_path),
    ]

    entries: list[dict] = []
    t0 = time.monotonic()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
    )

    def _on_sigint(signum, frame):
        # Não morre — só repassa pro filho e deixa ele salvar checkpoint
        print("\n\n⚠ Ctrl+C recebido. Pedindo ao mlx-lm pra parar (vai salvar último checkpoint)...\n",
              flush=True)
        try:
            proc.send_signal(signal.SIGINT)
        except Exception:
            pass

    old_handler = signal.signal(signal.SIGINT, _on_sigint)

    try:
        for line in proc.stdout:
            print(line, end="", flush=True)  # passthrough
            _parse_and_log(line, entries, t0)
        proc.wait()
    finally:
        signal.signal(signal.SIGINT, old_handler)

    return proc.returncode, entries, time.monotonic() - t0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Roda apenas 10 iters para validar o setup (≈2-3 min).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Caminho do YAML de config (default: finetuning/configs/lora_config.yaml).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Pula a confirmação interativa.",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"❌ Config não encontrada: {args.config}")
        return 1

    if not (HERE / "data" / "train.jsonl").exists():
        print("❌ finetuning/data/train.jsonl não existe.")
        print("   Rode antes: uv run python finetuning/prepare_mlx_dataset.py")
        return 1

    config = _load_config(args.config)
    _print_banner(config, args.smoke_test)

    if not args.yes:
        answer = input("Prosseguir? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            print("Cancelado.")
            return 0

    config_to_use = args.config
    if args.smoke_test:
        config_to_use = _build_smoke_config(config)
        print(f"\n→ Config de smoke test em: {config_to_use}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    code, entries, elapsed = _run_training(config_to_use)

    print("\n" + "=" * 64)
    print(f"Tempo total: {elapsed / 60:.1f} min  |  exit code: {code}")

    val_losses = [e for e in entries if e["type"] == "val"]
    if val_losses:
        best = min(val_losses, key=lambda e: e["val_loss"])
        print(f"Melhor val loss: {best['val_loss']:.4f} (iter {best['iter']})")
    else:
        print("⚠ Nenhuma medição de val loss encontrada na saída.")

    print(f"Log estruturado: {LOG_PATH.relative_to(HERE.parent)}")
    if not args.smoke_test:
        print(f"Adapter final:   {config['adapter_path']}/adapters.safetensors")
        print("\nPróximos passos:")
        print("  uv run python finetuning/plot_training.py")
        print("  uv run python finetuning/evaluate.py")
        print("  uv run python finetuning/chat.py")

    return code


if __name__ == "__main__":
    sys.exit(main())
