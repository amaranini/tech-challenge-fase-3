"""Schema SQLite do audit DB (Fase 6, Bloco 2).

4 tabelas principais:
- `interactions`        — uma linha por execução do grafo
- `guardrail_events`    — eventos de detecção/ação de guardrails
- `alerts`              — alertas de urgência alta emitidos
- `rag_retrievals`      — chunks retornados pelo RAG (com scores)

+ tabela `schema_meta` pra versionamento.

Por que SQLite local: zero deps externas, transacional, queryável via
CLI (sqlite3) e Python. Cabe em <100 MB pra uso clínico institucional
moderado. Migração pra Postgres é trivial quando crescer (Fase 7).

WAL mode pra suportar reads concorrentes (CLI lendo enquanto o grafo grava).

DEFENSIVO: o module-level constants definem o path default, mas o
AuditWriter aceita override pra testes (injeta tmp_path).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DB_PATH = _PROJECT_ROOT / "logging_" / "audit.db"

SCHEMA_VERSION = 2  # v2 (Fase 7): coluna `doctor_id` em interactions

# CREATE TABLEs — usar IF NOT EXISTS pra ser idempotente.
# Coluna `ts` em formato ISO 8601 (string) — SQLite não tem tipo DATETIME nativo,
# mas comparações lexicográficas sobre ISO 8601 funcionam corretamente.

_DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT UNIQUE NOT NULL,
    ts TEXT NOT NULL,
    question TEXT NOT NULL,
    patient_id TEXT,
    intent TEXT,
    urgency TEXT,
    bypass_detected INTEGER NOT NULL DEFAULT 0,
    response TEXT,
    latency_ms INTEGER,
    rag_has_sources INTEGER,
    doctor_id TEXT,             -- v2 (Fase 7): quem consultou (header X-Doctor-Id)
    state_snapshot TEXT  -- JSON do state completo (truncado se necessário)
);

CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(ts DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_patient ON interactions(patient_id);
CREATE INDEX IF NOT EXISTS idx_interactions_intent ON interactions(intent);

CREATE TABLE IF NOT EXISTS guardrail_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    guardrail_name TEXT NOT NULL,
    level TEXT NOT NULL,        -- 'warning' | 'block'
    applies_to TEXT NOT NULL,   -- 'input' | 'output'
    triggered INTEGER NOT NULL, -- 0/1
    matched_patterns TEXT,      -- JSON array
    severity REAL,
    message TEXT,
    action_taken TEXT,
    FOREIGN KEY (request_id) REFERENCES interactions(request_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_guardrail_request ON guardrail_events(request_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_name ON guardrail_events(guardrail_name);
CREATE INDEX IF NOT EXISTS idx_guardrail_triggered ON guardrail_events(triggered);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    patient_id TEXT,
    urgency TEXT NOT NULL,
    summary TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,   -- preparação Fase 7
    FOREIGN KEY (request_id) REFERENCES interactions(request_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alerts_request ON alerts(request_id);
CREATE INDEX IF NOT EXISTS idx_alerts_patient ON alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_alerts_ack ON alerts(acknowledged);

CREATE TABLE IF NOT EXISTS rag_retrievals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    query TEXT NOT NULL,
    top_k_results TEXT,         -- JSON: list[{source_file, section, score}]
    had_sources INTEGER NOT NULL,
    FOREIGN KEY (request_id) REFERENCES interactions(request_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rag_request ON rag_retrievals(request_id);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Aplica migrações leves pra DBs já existentes em versões antigas.

    SQLite suporta `ALTER TABLE ... ADD COLUMN` sem dor, então usamos isso
    pra colunas novas em versões maiores. Idempotente: checa a coluna antes
    de tentar adicionar.
    """
    # v1 → v2 (Fase 7): coluna `doctor_id` em interactions
    cols = {r[1] for r in conn.execute("PRAGMA table_info(interactions)").fetchall()}
    if "doctor_id" not in cols:
        conn.execute("ALTER TABLE interactions ADD COLUMN doctor_id TEXT")


def init_db(db_path: Path | str = AUDIT_DB_PATH) -> Path:
    """Inicializa o DB: cria tabelas se não existem, seta WAL mode,
    aplica migrações pendentes, insere/atualiza versão do schema. Idempotente.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        # WAL pra reads concorrentes (CLI vs grafo).
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_DDL)
        _migrate(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def get_schema_version(db_path: Path | str = AUDIT_DB_PATH) -> int | None:
    """Lê a versão do schema do DB. None se DB não existe ou não tem schema_meta."""
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT value FROM schema_meta WHERE key='version'")
        row = cur.fetchone()
        return int(row[0]) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
