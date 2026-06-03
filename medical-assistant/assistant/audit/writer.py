"""AuditWriter — grava execuções do grafo no audit DB (Fase 6, Bloco 2).

Filosofia: NUNCA pode crashar o grafo. Toda exceção é logada e engolida.

Uma chamada de `write_interaction(state, latency_ms)` gera, em UMA
transação:
- 1 linha em `interactions`
- N linhas em `guardrail_events` (1 por GuardrailResult, triggered ou não)
- M linhas em `alerts` (1 por alerta de urgência alta)
- 1 linha em `rag_retrievals` (se RAG foi executado)

Tudo na MESMA transação pra garantir consistência: ou tudo grava, ou nada.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from assistant.audit.schema import AUDIT_DB_PATH, init_db
from assistant.graph_state import MedicalState

logger = logging.getLogger(__name__)


# Limite do JSON state_snapshot — evita inflar o DB se algum nó devolver
# uma string gigante. ~50 KB é suficiente pra inspeção razoável.
_STATE_SNAPSHOT_MAX_BYTES = 50_000


class AuditWriter:
    """Escreve eventos de auditoria no audit DB.

    Lazy init: o DB só é tocado na primeira escrita. Permite injeção de
    `db_path` pra testes.

    Uso típico:
        writer = AuditWriter()  # path default
        writer.write_interaction(state, latency_ms=1234)

    Pode ser usado como singleton — mas instâncias separadas também são OK
    (cada chamada abre/fecha conexão própria; thread-safe para reads e writes
    via WAL).
    """

    def __init__(self, db_path: Path | str = AUDIT_DB_PATH):
        self.db_path = Path(db_path)
        self._initialized = False

    def _ensure_db(self) -> None:
        if self._initialized:
            return
        try:
            init_db(self.db_path)
            self._initialized = True
        except Exception as e:  # noqa: BLE001
            logger.exception("Audit init falhou — auditoria desabilitada: %s", e)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _safe_json(obj: Any, limit: int | None = None) -> str:
        """Serializa em JSON; trunca se exceder o limite."""
        try:
            s = json.dumps(obj, ensure_ascii=False, default=str)
            if limit and len(s.encode("utf-8")) > limit:
                # Trunca em UTF-8 sem cortar caractere no meio
                truncated = s.encode("utf-8")[:limit].decode("utf-8", errors="ignore")
                return truncated + "...[TRUNCATED]"
            return s
        except Exception as e:  # noqa: BLE001
            return json.dumps({"_serialization_error": str(e)})

    def write_interaction(
        self,
        state: MedicalState,
        latency_ms: int,
        doctor_id: str | None = None,
    ) -> bool:
        """Grava uma execução completa do grafo no DB.

        Retorna True se gravou com sucesso, False em caso de erro (loga
        a exceção mas não propaga). NÃO levanta — defensivo por design.

        `doctor_id`: identificador do médico que disparou a consulta (vem do
        header `X-Doctor-Id` na API). None quando a consulta foi via CLI.
        """
        self._ensure_db()
        if not self._initialized:
            return False

        try:
            self._write_atomic(state, latency_ms, doctor_id)
            return True
        except Exception as e:  # noqa: BLE001
            logger.exception("Audit write falhou pra request_id=%s: %s",
                             state.get("request_id"), e)
            return False

    def _write_atomic(
        self,
        state: MedicalState,
        latency_ms: int,
        doctor_id: str | None = None,
    ) -> None:
        """Escrita transacional. Pode levantar; só é chamado de write_interaction
        que captura.
        """
        request_id = state["request_id"]
        ts = self._now_iso()

        # Sanitiza o state_snapshot: omite os chunks completos do RAG
        # (texto duplicaria com rag_retrievals) e trunca campos longos.
        snapshot = dict(state)
        rag_chunks = snapshot.get("rag_chunks") or []
        snapshot["rag_chunks"] = [
            {k: v for k, v in c.items() if k != "text"}
            for c in rag_chunks
        ]
        snapshot_json = self._safe_json(snapshot, limit=_STATE_SNAPSHOT_MAX_BYTES)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:  # auto-commit/rollback
                # ─── interactions ───────────────────────────────────────
                conn.execute(
                    "INSERT INTO interactions "
                    "(request_id, ts, question, patient_id, intent, urgency, "
                    " bypass_detected, response, latency_ms, rag_has_sources, "
                    " doctor_id, state_snapshot) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request_id, ts,
                        state.get("question", ""),
                        state.get("patient_id"),
                        state.get("intent"),
                        state.get("urgency"),
                        1 if state.get("bypass_detected") else 0,
                        state.get("final_response"),
                        latency_ms,
                        1 if state.get("rag_has_sources") else 0,
                        doctor_id,
                        snapshot_json,
                    ),
                )

                # ─── guardrail_events (todos, triggered ou não) ─────────
                all_results = list(state.get("input_guardrails_triggered") or [])
                all_results.extend(state.get("output_guardrails_triggered") or [])
                for r in all_results:
                    conn.execute(
                        "INSERT INTO guardrail_events "
                        "(request_id, ts, guardrail_name, level, applies_to, "
                        " triggered, matched_patterns, severity, message, action_taken) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            request_id, ts,
                            r.get("guardrail_name", ""),
                            r.get("level", ""),
                            r.get("applies_to", ""),
                            1 if r.get("triggered") else 0,
                            self._safe_json(r.get("matched_patterns", [])),
                            float(r.get("severity") or 0.0),
                            r.get("message", ""),
                            r.get("action_taken"),
                        ),
                    )

                # ─── alerts ─────────────────────────────────────────────
                for a in (state.get("alerts_emitted") or []):
                    conn.execute(
                        "INSERT INTO alerts "
                        "(request_id, ts, patient_id, urgency, summary, acknowledged) "
                        "VALUES (?, ?, ?, ?, ?, 0)",
                        (
                            request_id,
                            a.get("timestamp") or ts,
                            a.get("patient_id"),
                            a.get("urgency", ""),
                            a.get("summary", ""),
                        ),
                    )

                # ─── rag_retrievals ─────────────────────────────────────
                # Só registra se algum nó RAG correu (rag_chunks pode ser
                # None se o caminho foi refuse/bypass — nesse caso, skip).
                if rag_chunks is not None and any(
                    t.get("node") == "retrieve_protocol"
                    for t in (state.get("node_trace") or [])
                ):
                    top_k = [
                        {
                            "source_file": c.get("source_file"),
                            "section": c.get("section"),
                            "score": c.get("score"),
                        }
                        for c in rag_chunks
                    ]
                    conn.execute(
                        "INSERT INTO rag_retrievals "
                        "(request_id, ts, query, top_k_results, had_sources) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            request_id, ts,
                            state.get("question", ""),
                            self._safe_json(top_k),
                            1 if state.get("rag_has_sources") else 0,
                        ),
                    )

            logger.info("Audit OK: request_id=%s (latency=%dms)", request_id, latency_ms)
        finally:
            conn.close()
