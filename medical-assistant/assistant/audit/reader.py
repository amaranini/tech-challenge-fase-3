"""AuditReader — consultas sobre o audit DB (Fase 6, Bloco 2).

Read-only. Cada método abre/fecha conexão própria (simples e seguro com
WAL mode habilitado pelo writer).

Métodos principais:
- list_recent(limit)               — últimas N interações
- get_by_id(request_id)            — interação + eventos + alerts + rag
- filter_by_patient(patient_id)
- filter_by_guardrail(name)
- filter_has_alerts()
- filter_has_guardrail()
- since(iso_date)
- stats()                          — agregados gerais
- tail_since(last_seen_id, limit)  — pra modo `tail` da CLI
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from assistant.audit.schema import AUDIT_DB_PATH


@dataclass
class InteractionRow:
    """Linha da tabela interactions, decodada."""

    id: int
    request_id: str
    ts: str
    question: str
    patient_id: str | None
    intent: str | None
    urgency: str | None
    bypass_detected: bool
    response: str | None
    latency_ms: int | None
    rag_has_sources: bool
    doctor_id: str | None         # v2 (Fase 7)
    state_snapshot: str | None    # JSON; chamador pode parsear se quiser

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "InteractionRow":
        # `doctor_id` pode estar ausente em DBs criados antes da v2 ou em
        # SELECTs que não trouxeram a coluna — defensivo.
        try:
            doctor_id = row["doctor_id"]
        except (IndexError, KeyError):
            doctor_id = None
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            ts=row["ts"],
            question=row["question"],
            patient_id=row["patient_id"],
            intent=row["intent"],
            urgency=row["urgency"],
            bypass_detected=bool(row["bypass_detected"]),
            response=row["response"],
            latency_ms=row["latency_ms"],
            rag_has_sources=bool(row["rag_has_sources"]),
            doctor_id=doctor_id,
            state_snapshot=row["state_snapshot"],
        )


@dataclass
class GuardrailEventRow:
    id: int
    request_id: str
    ts: str
    guardrail_name: str
    level: str
    applies_to: str
    triggered: bool
    matched_patterns: list  # decoded from JSON
    severity: float
    message: str
    action_taken: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "GuardrailEventRow":
        try:
            matched = json.loads(row["matched_patterns"] or "[]")
        except json.JSONDecodeError:
            matched = []
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            ts=row["ts"],
            guardrail_name=row["guardrail_name"],
            level=row["level"],
            applies_to=row["applies_to"],
            triggered=bool(row["triggered"]),
            matched_patterns=matched,
            severity=row["severity"] or 0.0,
            message=row["message"] or "",
            action_taken=row["action_taken"],
        )


@dataclass
class AlertRow:
    id: int
    request_id: str
    ts: str
    patient_id: str | None
    urgency: str
    summary: str
    acknowledged: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AlertRow":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            ts=row["ts"],
            patient_id=row["patient_id"],
            urgency=row["urgency"],
            summary=row["summary"] or "",
            acknowledged=bool(row["acknowledged"]),
        )


@dataclass
class InteractionDetail:
    """Resultado de `get_by_id`: linha + eventos + alerts + retrievals."""

    interaction: InteractionRow
    guardrail_events: list[GuardrailEventRow] = field(default_factory=list)
    alerts: list[AlertRow] = field(default_factory=list)
    rag_retrievals: list[dict] = field(default_factory=list)


class AuditReader:
    """Consultas read-only sobre o audit DB."""

    def __init__(self, db_path: Path | str = AUDIT_DB_PATH):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Listagens ──────────────────────────────────────────────────────

    def list_recent(self, limit: int = 10) -> list[InteractionRow]:
        """Últimas N interações por ID descendente (mais recentes primeiro)."""
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM interactions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def get_by_id(self, request_id: str) -> InteractionDetail | None:
        """Interação completa: linha principal + eventos + alerts + retrievals."""
        if not self.db_path.exists():
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM interactions WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                return None
            interaction = InteractionRow.from_row(row)

            events = [
                GuardrailEventRow.from_row(r)
                for r in conn.execute(
                    "SELECT * FROM guardrail_events WHERE request_id = ? ORDER BY id",
                    (request_id,),
                ).fetchall()
            ]
            alerts = [
                AlertRow.from_row(r)
                for r in conn.execute(
                    "SELECT * FROM alerts WHERE request_id = ? ORDER BY id",
                    (request_id,),
                ).fetchall()
            ]
            rag = [
                {
                    "id": r["id"], "ts": r["ts"], "query": r["query"],
                    "top_k_results": json.loads(r["top_k_results"] or "[]"),
                    "had_sources": bool(r["had_sources"]),
                }
                for r in conn.execute(
                    "SELECT * FROM rag_retrievals WHERE request_id = ? ORDER BY id",
                    (request_id,),
                ).fetchall()
            ]
            return InteractionDetail(
                interaction=interaction,
                guardrail_events=events,
                alerts=alerts,
                rag_retrievals=rag,
            )
        finally:
            conn.close()

    # ─── Filtros ────────────────────────────────────────────────────────

    def filter_by_patient(self, patient_id: str, limit: int = 50) -> list[InteractionRow]:
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM interactions WHERE patient_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (patient_id, limit),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def filter_by_guardrail(self, name: str, limit: int = 50) -> list[InteractionRow]:
        """Interações onde o guardrail X disparou (triggered=1)."""
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT i.* FROM interactions i "
                "JOIN guardrail_events e ON e.request_id = i.request_id "
                "WHERE e.guardrail_name = ? AND e.triggered = 1 "
                "ORDER BY i.id DESC LIMIT ?",
                (name, limit),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def filter_has_alerts(self, limit: int = 50) -> list[InteractionRow]:
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT i.* FROM interactions i "
                "JOIN alerts a ON a.request_id = i.request_id "
                "ORDER BY i.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def filter_has_guardrail(self, limit: int = 50) -> list[InteractionRow]:
        """Interações com QUALQUER guardrail disparado."""
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT i.* FROM interactions i "
                "JOIN guardrail_events e ON e.request_id = i.request_id "
                "WHERE e.triggered = 1 "
                "ORDER BY i.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def since(self, iso_date: str, limit: int = 100) -> list[InteractionRow]:
        """Interações com ts >= iso_date (string ISO 8601)."""
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM interactions WHERE ts >= ? "
                "ORDER BY id DESC LIMIT ?",
                (iso_date, limit),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    def tail_since(self, last_seen_id: int, limit: int = 20) -> list[InteractionRow]:
        """Pra modo `tail` da CLI: retorna interações com id > last_seen_id."""
        if not self.db_path.exists():
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM interactions WHERE id > ? "
                "ORDER BY id ASC LIMIT ?",
                (last_seen_id, limit),
            ).fetchall()
            return [InteractionRow.from_row(r) for r in rows]
        finally:
            conn.close()

    # ─── Estatísticas ───────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Agregados sobre todo o histórico — total, % com guardrail/alerta, latência."""
        if not self.db_path.exists():
            return {
                "total_interactions": 0,
                "with_guardrail_triggered": 0,
                "with_alert": 0,
                "bypass_attempts": 0,
                "avg_latency_ms": 0,
                "by_intent": {},
                "by_urgency": {},
                "by_guardrail": {},
            }
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            with_guard = conn.execute(
                "SELECT COUNT(DISTINCT request_id) FROM guardrail_events "
                "WHERE triggered = 1"
            ).fetchone()[0]
            with_alert = conn.execute(
                "SELECT COUNT(DISTINCT request_id) FROM alerts"
            ).fetchone()[0]
            bypass = conn.execute(
                "SELECT COUNT(*) FROM interactions WHERE bypass_detected = 1"
            ).fetchone()[0]
            avg_lat = conn.execute(
                "SELECT AVG(latency_ms) FROM interactions WHERE latency_ms IS NOT NULL"
            ).fetchone()[0] or 0
            by_intent = {
                r[0] or "(none)": r[1]
                for r in conn.execute(
                    "SELECT intent, COUNT(*) FROM interactions GROUP BY intent"
                ).fetchall()
            }
            by_urgency = {
                r[0] or "(none)": r[1]
                for r in conn.execute(
                    "SELECT urgency, COUNT(*) FROM interactions GROUP BY urgency"
                ).fetchall()
            }
            by_guardrail = {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT guardrail_name, COUNT(*) FROM guardrail_events "
                    "WHERE triggered = 1 GROUP BY guardrail_name "
                    "ORDER BY COUNT(*) DESC"
                ).fetchall()
            }
            return {
                "total_interactions": total,
                "with_guardrail_triggered": with_guard,
                "with_alert": with_alert,
                "bypass_attempts": bypass,
                "avg_latency_ms": int(avg_lat),
                "by_intent": by_intent,
                "by_urgency": by_urgency,
                "by_guardrail": by_guardrail,
            }
        finally:
            conn.close()
