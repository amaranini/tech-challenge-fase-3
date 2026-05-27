"""Converte data/processed/{train,val,test}.jsonl para finetuning/data/{train,valid,test}.jsonl.

O mlx-lm aceita o formato "chat" (linhas no formato `{"messages": [...]}`) que é
exatamente o que `prepare_dataset.py` da Fase 1 já produziu. Logo, a conversão é
basicamente:

1. Copiar `data/processed/train.jsonl` → `finetuning/data/train.jsonl`
2. Copiar `data/processed/val.jsonl`   → `finetuning/data/valid.jsonl`   (rename)
3. Copiar `data/processed/test.jsonl`  → `finetuning/data/test.jsonl`

O mlx-lm exige especificamente o nome `valid.jsonl` (não `val.jsonl`). Por isso o
rename. Também validamos cada linha — se algum item estiver fora de formato,
descartamos com aviso.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "processed"
DEST_DIR = HERE / "data"

# Mapeamento: arquivo fonte → arquivo destino (note val → valid).
RENAME_MAP = {
    "train.jsonl": "train.jsonl",
    "val.jsonl": "valid.jsonl",
    "test.jsonl": "test.jsonl",
}


def _validate_line(line: str) -> dict | None:
    """Retorna o objeto se a linha for um JSON válido com `messages`, senão None."""
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or "messages" not in obj:
        return None
    msgs = obj["messages"]
    if not isinstance(msgs, list) or not msgs:
        return None
    for m in msgs:
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            return None
    return obj


def convert_file(src: Path, dst: Path) -> tuple[int, int]:
    """Copia src → dst, validando cada linha. Retorna (ok, descartados)."""
    ok = 0
    skipped = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for i, line in enumerate(fin, start=1):
            obj = _validate_line(line)
            if obj is None:
                skipped += 1
                print(f"  ⚠ linha {i} de {src.name} descartada (formato inválido)")
                continue
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            ok += 1
    return ok, skipped


def main() -> int:
    print("=" * 60)
    print("Preparação do dataset para mlx-lm")
    print("=" * 60)

    if not SOURCE_DIR.exists():
        print(f"❌ {SOURCE_DIR.relative_to(PROJECT_ROOT)} não existe.")
        print("   Rode antes: uv run python data/prepare_dataset.py")
        return 1

    missing = [name for name in RENAME_MAP if not (SOURCE_DIR / name).exists()]
    if missing:
        print(f"❌ Arquivos faltando em {SOURCE_DIR.relative_to(PROJECT_ROOT)}: {missing}")
        print("   Rode antes: uv run python data/prepare_dataset.py")
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    total_skipped = 0
    for src_name, dst_name in RENAME_MAP.items():
        src = SOURCE_DIR / src_name
        dst = DEST_DIR / dst_name
        print(f"\n→ {src_name} → {dst_name}")
        ok, skipped = convert_file(src, dst)
        total_ok += ok
        total_skipped += skipped
        print(f"  {ok} linhas convertidas, {skipped} descartadas")

    print("\n" + "=" * 60)
    print(f"Total: {total_ok} exemplos prontos para mlx-lm em {DEST_DIR.relative_to(PROJECT_ROOT)}")
    if total_skipped:
        print(f"⚠ {total_skipped} linhas descartadas (verifique o aviso acima)")
    print("\nPróximo passo (smoke test): uv run python finetuning/train.py --smoke-test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
