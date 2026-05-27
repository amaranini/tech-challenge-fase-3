"""Constrói o banco SQLite de pacientes a partir do CSV sintético.

Lê `data/synthetic/patients.csv`, calcula a idade a partir da data de
nascimento, e popula `assistant/data/patients.db` com schema fixo.

Idempotente: drop & recreate da tabela a cada execução.

Uso:
    uv run python assistant/tools/build_patient_db.py
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "synthetic" / "patients.csv"
DB_PATH = PROJECT_ROOT / "assistant" / "data" / "patients.db"

SCHEMA_SQL = """
CREATE TABLE pacientes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    idade INTEGER NOT NULL,
    sexo TEXT NOT NULL,
    alergias TEXT,
    medicacoes_atuais TEXT,
    historico_resumido TEXT,
    exames_pendentes TEXT DEFAULT '[]'
);
"""


def _calculate_age(birth_date_str: str) -> int:
    """Calcula idade a partir de data DD/MM/AAAA."""
    dt = datetime.strptime(birth_date_str, "%d/%m/%Y").date()
    today = date.today()
    return today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))


def main() -> int:
    if not CSV_PATH.exists():
        print(f"❌ {CSV_PATH.relative_to(PROJECT_ROOT)} não existe.")
        print("   Gere os pacientes antes: uv run python data/generate_synthetic.py")
        return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("  Construção do banco de pacientes")
    print("=" * 64)
    print(f"  CSV:   {CSV_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  DB:    {DB_PATH.relative_to(PROJECT_ROOT)}")
    print()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS pacientes")
    cur.executescript(SCHEMA_SQL)

    inserted = 0
    skipped = 0
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                age = _calculate_age(row["data_nascimento"])
            except (KeyError, ValueError) as e:
                print(f"  ⚠ pulando {row.get('id', '?')}: {e}")
                skipped += 1
                continue
            try:
                cur.execute(
                    "INSERT INTO pacientes "
                    "(id, nome, idade, sexo, alergias, medicacoes_atuais, "
                    " historico_resumido, exames_pendentes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, '[]')",
                    (
                        row["id"],
                        row["nome"],
                        age,
                        row["sexo"],
                        row.get("alergias", ""),
                        row.get("medicacoes_atuais", ""),
                        row.get("historico_resumido", ""),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError as e:
                print(f"  ⚠ duplicado {row.get('id', '?')}: {e}")
                skipped += 1

    conn.commit()

    # Estatísticas
    cur.execute("SELECT COUNT(*) FROM pacientes")
    total = cur.fetchone()[0]
    cur.execute("SELECT AVG(idade), MIN(idade), MAX(idade) FROM pacientes")
    avg_age, min_age, max_age = cur.fetchone()
    cur.execute("SELECT sexo, COUNT(*) FROM pacientes GROUP BY sexo")
    by_sex = dict(cur.fetchall())
    conn.close()

    print(f"✅ {inserted} pacientes inseridos, {skipped} pulados")
    print(f"   Total no DB: {total}")
    print(f"   Idade: média {avg_age:.0f}, min {min_age}, max {max_age}")
    print(f"   Sexo:  {by_sex}")
    print()
    print("Smoke test:")
    print("   uv run python -m assistant.tools.patient_records P0001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
