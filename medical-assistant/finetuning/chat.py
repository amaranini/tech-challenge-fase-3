"""Chat interativo no terminal com o modelo fine-tuned (ou base).

Uso:
    uv run python finetuning/chat.py             # carrega adapter (fine-tuned)
    uv run python finetuning/chat.py --base      # carrega só o modelo base

Dentro do chat, comandos:
    /sair       — encerra
    /limpar     — limpa o histórico de conversa
    /sistema X  — redefine a system message
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "configs" / "lora_config.yaml"
ADAPTER_PATH = HERE / "output" / "adapters"

DEFAULT_SYSTEM = (
    "Você é um assistente médico que responde com base em protocolos clínicos "
    "institucionais. Seja preciso e estruturado. Em situações que exijam "
    "avaliação presencial, oriente buscar atendimento profissional."
)
MAX_NEW_TOKENS = 500


def _load_model(model_path: str, adapter: Path | None):
    from mlx_lm import load
    if adapter is not None:
        print(f"→ Carregando modelo base + adapter ({adapter.relative_to(HERE.parent)})...")
        return load(model_path, adapter_path=str(adapter))
    print("→ Carregando modelo BASE (sem adapter)...")
    return load(model_path)


def _chat_loop(model, tokenizer, system_prompt: str) -> None:
    from mlx_lm import generate
    history: list[dict] = [{"role": "system", "content": system_prompt}]
    print("\nDigite sua mensagem. Comandos: /sair, /limpar, /sistema <texto>.\n")

    while True:
        try:
            user = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté.")
            return

        if not user:
            continue
        if user.lower() in ("/sair", "sair", "/exit", "exit", "/quit", "quit"):
            print("Até.")
            return
        if user.lower() == "/limpar":
            history = [{"role": "system", "content": system_prompt}]
            print("(histórico limpo)\n")
            continue
        if user.lower().startswith("/sistema "):
            system_prompt = user[len("/sistema "):].strip()
            history = [{"role": "system", "content": system_prompt}]
            print("(system message atualizada e histórico limpo)\n")
            continue

        history.append({"role": "user", "content": user})
        formatted = tokenizer.apply_chat_template(
            history, tokenize=False, add_generation_prompt=True
        )

        t0 = time.monotonic()
        try:
            response = generate(
                model, tokenizer,
                prompt=formatted,
                max_tokens=MAX_NEW_TOKENS,
                verbose=False,
            )
        except KeyboardInterrupt:
            print("\n(geração interrompida)\n")
            history.pop()  # remove a mensagem do usuário que não foi respondida
            continue
        elapsed = time.monotonic() - t0
        response = response.strip()
        history.append({"role": "assistant", "content": response})
        print(f"\nAssistente ({elapsed:.1f}s): {response}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat com o modelo fine-tuned.")
    parser.add_argument(
        "--base",
        action="store_true",
        help="Carrega só o modelo base, sem o adapter LoRA.",
    )
    parser.add_argument(
        "--system",
        type=str,
        default=DEFAULT_SYSTEM,
        help="System message inicial (default: assistente médico padrão).",
    )
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        print(f"❌ {CONFIG_PATH} não existe.")
        return 1
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    model_path = config["model"]

    if not args.base and not ADAPTER_PATH.exists():
        print(f"❌ Adapter não encontrado em {ADAPTER_PATH}.")
        print("   Use --base para conversar com o modelo cru, ou rode antes:")
        print("   uv run python finetuning/train.py")
        return 1

    adapter = None if args.base else ADAPTER_PATH
    model, tokenizer = _load_model(model_path, adapter)
    print(f"✓ Modelo carregado: {model_path}{' + adapter' if adapter else ' (base)'}\n")

    _chat_loop(model, tokenizer, args.system)
    return 0


if __name__ == "__main__":
    sys.exit(main())
