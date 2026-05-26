"""Inspeciona N amostras aleatórias de um split do dataset.

Uso:
    uv run python data/inspect_dataset.py --split train --n 5
    uv run python data/inspect_dataset.py --split val --n 3
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROCESSED_DIR = HERE / "processed"

# Caracteres para o cabeçalho visual (largura 70).
BAR = "═" * 70
SEP = "─" * 70


def load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def pretty_print_item(idx: int, total: int, item: dict) -> None:
    print(BAR)
    print(f"  Amostra {idx + 1}/{total}")
    print(BAR)
    for msg in item["messages"]:
        role = msg["role"].upper()
        content = msg["content"]
        print(f"\n[{role}]")
        print(SEP)
        # Quebra linhas longas em ~76 colunas para legibilidade
        print(content)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspeciona amostras do dataset.")
    parser.add_argument("--split", choices=["train", "val", "test"], default="train")
    parser.add_argument("--n", type=int, default=5, help="quantas amostras mostrar")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed do random (default: aleatório de verdade)")
    args = parser.parse_args()

    path = PROCESSED_DIR / f"{args.split}.jsonl"
    if not path.exists():
        print(f"❌ {path} não existe. Rode antes:")
        print("   uv run python data/prepare_dataset.py")
        return 1

    items = load_jsonl(path)
    if not items:
        print(f"⚠ {path} está vazio.")
        return 1

    n = min(args.n, len(items))
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    sample = rng.sample(items, n)

    print(f"\nMostrando {n} amostra(s) aleatória(s) de {args.split}.jsonl ({len(items)} totais)\n")
    for i, item in enumerate(sample):
        pretty_print_item(i, n, item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
