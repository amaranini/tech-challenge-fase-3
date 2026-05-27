"""Inspeciona amostras do dataset (train/val/test) ou um arquivo JSONL avulso.

Exemplos:
    # 5 amostras aleatórias do train (default)
    uv run python data/inspect_dataset.py --split train --n 5

    # 10 amostras só do assistant
    uv run python data/inspect_dataset.py --split val --n 10 --show assistant

    # Conta + mostra linhas onde a resposta do assistant contém o padrão
    uv run python data/inspect_dataset.py --split train --grep "não posso"

    # Inspeciona arquivo JSONL fora dos splits (ex: o refusals.jsonl bruto)
    uv run python data/inspect_dataset.py --file data/synthetic/refusals.jsonl --n 5

    # Estatísticas de fontes (via system message dos exemplos)
    uv run python data/inspect_dataset.py --split train --source-stats
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
PROCESSED_DIR = HERE / "processed"

BAR = "═" * 70
SEP = "─" * 70

# Mapeamento de pedaços únicos do system message → rótulo do source_type.
# Usa um trecho discriminante do início de cada SYSTEM_X em prepare_dataset.py.
SYSTEM_FINGERPRINTS: list[tuple[str, str]] = [
    ("protocolos clínicos institucionais", "protocol"),
    ("redigir documentos clínicos", "template"),
    ("resume informações de prontuários", "patient"),
    ("especializado em prática clínica", "qa"),
    ("prioriza segurança e ética clínica", "refusal"),
]


def load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _normalize_item(rec: dict) -> dict:
    """Aceita tanto items com `messages` (splits processados) quanto
    pares brutos com `pergunta`/`resposta` (refusals.jsonl, qa_pairs.jsonl).

    Devolve sempre dict com chave `messages` pra simplificar o resto.
    """
    if "messages" in rec:
        return rec
    if "pergunta" in rec and "resposta" in rec:
        msgs = [
            {"role": "user", "content": rec["pergunta"]},
            {"role": "assistant", "content": rec["resposta"]},
        ]
        return {"messages": msgs, "_raw": rec}
    # fallback: devolve como veio (pode quebrar abaixo, mas é o esperado)
    return rec


def _infer_source(item: dict) -> str:
    """Identifica o source_type a partir do system message."""
    for msg in item["messages"]:
        if msg["role"] != "system":
            continue
        content = msg["content"].lower()
        for fingerprint, label in SYSTEM_FINGERPRINTS:
            if fingerprint.lower() in content:
                return label
    return "unknown"


def _assistant_text(item: dict) -> str:
    return " ".join(
        m["content"] for m in item["messages"] if m["role"] == "assistant"
    )


def _user_text(item: dict) -> str:
    return " ".join(
        m["content"] for m in item["messages"] if m["role"] == "user"
    )


def _matches_grep(item: dict, pattern: str, where: str) -> bool:
    pat = pattern.lower()
    if where in ("assistant", "all"):
        if pat in _assistant_text(item).lower():
            return True
    if where in ("user", "all"):
        if pat in _user_text(item).lower():
            return True
    if where == "system":
        for m in item["messages"]:
            if m["role"] == "system" and pat in m["content"].lower():
                return True
    return False


def pretty_print_item(
    idx: int, total: int, item: dict, show: str, full: bool
) -> None:
    print(BAR)
    print(f"  Amostra {idx + 1}/{total}")
    print(BAR)
    for msg in item["messages"]:
        role = msg["role"]
        if show != "all" and role != show:
            continue
        content = msg["content"]
        if not full and len(content) > 600:
            content = content[:600] + " […]"
        print(f"\n[{role.upper()}]")
        print(SEP)
        print(content)
    print()


def cmd_source_stats(items: list[dict]) -> None:
    """Conta exemplos por source_type inferido do system message."""
    from collections import Counter
    counts = Counter(_infer_source(it) for it in items)
    total = sum(counts.values())
    print(f"\nTotal: {total} exemplos\n")
    print(f"{'source_type':<20} {'count':>6}  {'%':>6}")
    print(SEP)
    for src, cnt in counts.most_common():
        pct = 100 * cnt / total if total else 0
        print(f"{src:<20} {cnt:>6}  {pct:>5.1f}%")
    print()


def cmd_grep(items: list[dict], pattern: str, where: str, show: str,
             full: bool, n: int | None) -> None:
    """Filtra items que contêm o padrão; mostra contagem + amostras."""
    matches = [it for it in items if _matches_grep(it, pattern, where)]
    print(f"\nPadrão '{pattern}' em [{where}]: "
          f"{len(matches)}/{len(items)} exemplos\n")
    if not matches:
        return
    if n is not None and n < len(matches):
        sample = random.Random(42).sample(matches, n)
        print(f"Mostrando {n} aleatórias (seed=42):\n")
    else:
        sample = matches
        print(f"Mostrando todas as {len(sample)}:\n")
    for i, item in enumerate(sample):
        pretty_print_item(i, len(sample), item, show, full)


def cmd_sample(items: list[dict], n: int, seed: int | None,
               show: str, full: bool) -> None:
    """Mostra N amostras aleatórias."""
    n = min(n, len(items))
    rng = random.Random(seed) if seed is not None else random.Random()
    sample = rng.sample(items, n)
    print(f"\nMostrando {n} amostra(s) aleatória(s) de {len(items)} total(is)\n")
    for i, item in enumerate(sample):
        pretty_print_item(i, n, item, show, full)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspeciona amostras do dataset.")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--split", choices=["train", "val", "test"], default=None,
                     help="qual split inspecionar (default: train se nenhum dos dois)")
    src.add_argument("--file", type=Path, default=None,
                     help="caminho pra um JSONL avulso (ex: data/synthetic/refusals.jsonl)")

    parser.add_argument("--n", type=int, default=5, help="quantas amostras mostrar")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed do random (default: aleatório de verdade)")
    parser.add_argument("--show", choices=["all", "system", "user", "assistant"],
                        default="all", help="que parte do exemplo exibir")
    parser.add_argument("--full", action="store_true",
                        help="mostra conteúdo completo (sem truncamento de 600 chars)")
    parser.add_argument("--grep", type=str, default=None,
                        help="filtra/conta exemplos cujo conteúdo contém este padrão")
    parser.add_argument("--grep-where",
                        choices=["assistant", "user", "system", "all"],
                        default="assistant",
                        help="onde procurar o --grep (default: assistant)")
    parser.add_argument("--source-stats", action="store_true",
                        help="conta exemplos por source_type (via system message)")
    args = parser.parse_args()

    # Resolve a fonte.
    if args.file is not None:
        path = args.file
    else:
        split = args.split or "train"
        path = PROCESSED_DIR / f"{split}.jsonl"
    if not path.exists():
        print(f"❌ {path} não existe.")
        if args.file is None:
            print("   Rode antes: uv run python data/prepare_dataset.py")
        return 1

    items_raw = load_jsonl(path)
    if not items_raw:
        print(f"⚠ {path} está vazio.")
        return 1
    items = [_normalize_item(it) for it in items_raw]

    # Dispatch.
    if args.source_stats:
        cmd_source_stats(items)
        return 0
    if args.grep is not None:
        cmd_grep(
            items, args.grep, args.grep_where, args.show, args.full,
            n=args.n if args.n > 0 else None,
        )
        return 0
    cmd_sample(items, args.n, args.seed, args.show, args.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
