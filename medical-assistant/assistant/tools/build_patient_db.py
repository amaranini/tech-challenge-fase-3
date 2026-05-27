"""Constrói o banco SQLite de pacientes a partir do CSV sintético.

Lê `data/synthetic/patients.csv`, calcula a idade a partir da data de
nascimento, e popula `assistant/data/patients.db` com schema fixo.

Idempotente: drop & recreate da tabela a cada execução.

Uso:
    uv run python assistant/tools/build_patient_db.py
"""

from __future__ import annotations

import csv
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
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

CREATE TABLE exames_pendentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    tipo_exame TEXT NOT NULL,
    data_solicitacao DATE NOT NULL,
    prioridade TEXT NOT NULL CHECK(prioridade IN ('rotina','urgente','imediato')),
    FOREIGN KEY (patient_id) REFERENCES pacientes(id) ON DELETE CASCADE
);

CREATE INDEX idx_exames_patient ON exames_pendentes(patient_id);
"""

# Vocabulário de exames (não usamos Faker porque queremos termos clínicos
# em pt-BR, e Faker gera só vocabulário genérico).
EXAM_TYPES = (
    "Hemograma completo",
    "Raio-X de tórax",
    "Eletrocardiograma (ECG)",
    "Glicemia de jejum",
    "Função renal (ureia/creatinina)",
    "TSH e T4 livre",
    "Urina tipo 1",
    "Tomografia de crânio",
    "Holter 24h",
    "Hemocultura",
    "Ecocardiograma",
    "Ultrassom abdominal",
)

# Distribuição: muitos pacientes com 0-1 exame, poucos com 3.
EXAM_COUNT_DIST = (
    (0, 0.30),
    (1, 0.40),
    (2, 0.20),
    (3, 0.10),
)
# Distribuição de prioridade.
EXAM_PRIORITY_DIST = (
    ("rotina", 0.60),
    ("urgente", 0.30),
    ("imediato", 0.10),
)


def _weighted_choice(items_with_weight: tuple, rng: random.Random):
    items = [i[0] for i in items_with_weight]
    weights = [i[1] for i in items_with_weight]
    return rng.choices(items, weights=weights, k=1)[0]


def _seed_pending_exams(cur: sqlite3.Cursor, patient_ids: list[str], rng: random.Random) -> tuple[int, dict]:
    """Popula a tabela exames_pendentes pra cada paciente.

    Retorna (total_inserted, dist_counts) — dist_counts conta quantos
    pacientes ficaram com 0, 1, 2, 3 exames (pra estatística no print).
    """
    today = date.today()
    total = 0
    count_dist = {0: 0, 1: 0, 2: 0, 3: 0}
    for pid in patient_ids:
        n_exames = _weighted_choice(EXAM_COUNT_DIST, rng)
        count_dist[n_exames] += 1
        for _ in range(n_exames):
            tipo = rng.choice(EXAM_TYPES)
            days_ago = rng.randint(0, 30)
            data_solic = today - timedelta(days=days_ago)
            prioridade = _weighted_choice(EXAM_PRIORITY_DIST, rng)
            cur.execute(
                "INSERT INTO exames_pendentes "
                "(patient_id, tipo_exame, data_solicitacao, prioridade) "
                "VALUES (?, ?, ?, ?)",
                (pid, tipo, data_solic.isoformat(), prioridade),
            )
            total += 1
    return total, count_dist


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
    cur.execute("DROP TABLE IF EXISTS exames_pendentes")
    cur.execute("DROP TABLE IF EXISTS pacientes")
    cur.executescript(SCHEMA_SQL)

    inserted = 0
    skipped = 0
    inserted_ids: list[str] = []
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
                inserted_ids.append(row["id"])
            except sqlite3.IntegrityError as e:
                print(f"  ⚠ duplicado {row.get('id', '?')}: {e}")
                skipped += 1

    # Populando exames_pendentes (seed fixo p/ reprodutibilidade).
    rng = random.Random(42)
    n_exams, count_dist = _seed_pending_exams(cur, inserted_ids, rng)

    conn.commit()

    # Estatísticas
    cur.execute("SELECT COUNT(*) FROM pacientes")
    total = cur.fetchone()[0]
    cur.execute("SELECT AVG(idade), MIN(idade), MAX(idade) FROM pacientes")
    avg_age, min_age, max_age = cur.fetchone()
    cur.execute("SELECT sexo, COUNT(*) FROM pacientes GROUP BY sexo")
    by_sex = dict(cur.fetchall())
    cur.execute("SELECT prioridade, COUNT(*) FROM exames_pendentes GROUP BY prioridade")
    by_prio = dict(cur.fetchall())
    conn.close()

    print(f"✅ {inserted} pacientes inseridos, {skipped} pulados")
    print(f"   Total no DB: {total}")
    print(f"   Idade: média {avg_age:.0f}, min {min_age}, max {max_age}")
    print(f"   Sexo:  {by_sex}")
    print()
    print(f"✅ {n_exams} exames pendentes criados")
    print(f"   Pacientes com 0 exames: {count_dist[0]}")
    print(f"   Pacientes com 1 exame:  {count_dist[1]}")
    print(f"   Pacientes com 2 exames: {count_dist[2]}")
    print(f"   Pacientes com 3 exames: {count_dist[3]}")
    print(f"   Por prioridade: {by_prio}")
    print()
    print("Smoke test:")
    print("   uv run python -m assistant.tools.patient_records P0001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
