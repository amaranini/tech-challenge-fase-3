"""Auditoria estruturada do assistente (Fase 6, Bloco 2).

- `AuditWriter` grava cada execução do grafo em SQLite (4 tabelas).
- `AuditReader` consulta interações, eventos, alerts, retrievals.
- CLI: `uv run python -m assistant.audit list/show/filter/stats/tail/export`.

DB local em `logging_/audit.db`. WAL mode pra reads concorrentes.
Writer é DEFENSIVO: falhas são logadas mas nunca propagam.
"""

from assistant.audit.reader import (
    AlertRow,
    AuditReader,
    GuardrailEventRow,
    InteractionDetail,
    InteractionRow,
)
from assistant.audit.schema import AUDIT_DB_PATH, init_db
from assistant.audit.writer import AuditWriter

__all__ = [
    "AuditWriter",
    "AuditReader",
    "InteractionRow",
    "InteractionDetail",
    "GuardrailEventRow",
    "AlertRow",
    "AUDIT_DB_PATH",
    "init_db",
]
