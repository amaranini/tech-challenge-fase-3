"""Testes do AuditWriter (Fase 6, Bloco 2)."""

from __future__ import annotations

import sqlite3

import pytest

from assistant.audit.schema import SCHEMA_VERSION, get_schema_version, init_db
from assistant.audit.writer import AuditWriter
from assistant.graph_state import initial_state


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "audit.db"


@pytest.fixture
def writer(db_path):
    return AuditWriter(db_path)


def _make_state(**overrides):
    state = initial_state("Pergunta de teste", patient_id=overrides.pop("patient_id", None))
    for k, v in overrides.items():
        state[k] = v
    return state


class TestSchemaInit:
    def test_init_db_cria_arquivo(self, db_path):
        init_db(db_path)
        assert db_path.exists()
        assert get_schema_version(db_path) == SCHEMA_VERSION

    def test_init_db_idempotente(self, db_path):
        init_db(db_path)
        init_db(db_path)  # 2ª vez não deve falhar
        assert get_schema_version(db_path) == SCHEMA_VERSION

    def test_get_version_em_db_inexistente(self, tmp_path):
        assert get_schema_version(tmp_path / "nao_existe.db") is None

    def test_wal_mode_ativo(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()


class TestWriteInteraction:
    def test_grava_basico(self, writer, db_path):
        state = _make_state(intent="clinica", urgency="baixa",
                            final_response="OK", patient_id="P0001")
        ok = writer.write_interaction(state, latency_ms=1234)
        assert ok is True
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute("SELECT * FROM interactions").fetchall()
            assert len(rows) == 1
            row = rows[0]
            assert row[1] == state["request_id"]  # request_id
            assert row[3] == "Pergunta de teste"  # question
        finally:
            conn.close()

    def test_grava_guardrails_triggered_e_nao_triggered(self, writer, db_path):
        state = _make_state(
            output_guardrails_triggered=[
                {"guardrail_name": "prescricao_direta", "triggered": True,
                 "level": "block", "applies_to": "output",
                 "matched_patterns": ["verb_dose:Prescreva..."],
                 "severity": 0.9, "message": "x", "action_taken": "rewritten"},
                {"guardrail_name": "diagnostico_definitivo", "triggered": False,
                 "level": "block", "applies_to": "output",
                 "matched_patterns": [], "severity": 0.0, "message": "",
                 "action_taken": None},
            ],
        )
        writer.write_interaction(state, latency_ms=1000)
        conn = sqlite3.connect(db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM guardrail_events").fetchone()[0]
            assert n == 2
            n_trig = conn.execute(
                "SELECT COUNT(*) FROM guardrail_events WHERE triggered = 1"
            ).fetchone()[0]
            assert n_trig == 1
        finally:
            conn.close()

    def test_grava_alerts(self, writer, db_path):
        state = _make_state(
            urgency="alta",
            alerts_emitted=[
                {"timestamp": "2026-01-01", "patient_id": "P0001",
                 "question": "q", "urgency": "alta", "summary": "sep"}
            ],
        )
        writer.write_interaction(state, latency_ms=500)
        conn = sqlite3.connect(db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            assert n == 1
            ack = conn.execute("SELECT acknowledged FROM alerts").fetchone()[0]
            assert ack == 0  # default false
        finally:
            conn.close()

    def test_grava_rag_retrieval_se_no_trace(self, writer, db_path):
        state = _make_state(
            rag_has_sources=True,
            rag_chunks=[{"text": "very long text here that gets stripped",
                         "source_file": "p.md", "section": "X", "score": 0.85}],
            node_trace=[{"node": "retrieve_protocol", "timestamp": "x",
                         "latency_s": 0.1, "summary": "s", "error": None}],
        )
        writer.write_interaction(state, latency_ms=500)
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute("SELECT * FROM rag_retrievals").fetchall()
            assert len(rows) == 1
            # top_k_results NÃO deve incluir o texto longo (só metadados)
            import json
            top_k = json.loads(rows[0][4])
            assert "text" not in top_k[0]
            assert top_k[0]["source_file"] == "p.md"
        finally:
            conn.close()

    def test_skipped_rag_se_node_nao_executou(self, writer, db_path):
        # Caminho refuse/bypass — retrieve_protocol não executou
        state = _make_state(rag_chunks=None, node_trace=[
            {"node": "input_guardrail_check", "timestamp": "x",
             "latency_s": 0.1, "summary": "s", "error": None},
        ])
        writer.write_interaction(state, latency_ms=500)
        conn = sqlite3.connect(db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM rag_retrievals").fetchone()[0]
            assert n == 0
        finally:
            conn.close()

    def test_state_snapshot_omite_texto_dos_chunks(self, writer, db_path):
        state = _make_state(
            rag_chunks=[{"text": "X" * 5000, "source_file": "p.md",
                         "section": "S", "score": 0.8}],
            node_trace=[{"node": "retrieve_protocol", "timestamp": "x",
                         "latency_s": 0.1, "summary": "s", "error": None}],
        )
        writer.write_interaction(state, latency_ms=500)
        conn = sqlite3.connect(db_path)
        try:
            snap = conn.execute(
                "SELECT state_snapshot FROM interactions"
            ).fetchone()[0]
            assert "X" * 100 not in snap  # texto longo dos chunks foi removido
        finally:
            conn.close()


class TestDefensive:
    """O writer NUNCA pode crashar o grafo."""

    def test_db_em_path_invalido_nao_propaga(self, tmp_path):
        # Path "inválido" — DB dentro de diretório que não pode ser criado
        # (ex: subdir de /dev/null). Cria-se o diretório, mas tentamos com
        # um path obviamente impossível de escrever (caracteres ruins).
        writer = AuditWriter(tmp_path / "\x00bad" / "audit.db")
        state = _make_state()
        # Não deve levantar
        ok = writer.write_interaction(state, latency_ms=500)
        assert ok is False  # falhou silenciosamente

    def test_state_com_objeto_nao_serializavel_ainda_funciona(self, writer, db_path):
        # Coloca um objeto não-serializável no state — o safe_json captura
        class _Bizarro:
            pass
        state = _make_state()
        state["patient_data"] = {"weird": _Bizarro()}
        ok = writer.write_interaction(state, latency_ms=500)
        # Pode gravar com state_snapshot = JSON com default=str do bizarro
        assert ok is True
