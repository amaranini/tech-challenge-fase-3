"""Testes da API HTTP (Fase 7, Bloco A).

Filosofia: testes rápidos NÃO carregam o modelo. Usam:
- `app.state.skip_warmup = True` pra pular o lifespan pesado
- `app.dependency_overrides[run_graph_callable]` pra mockar o grafo

Os testes lentos (`@slow`) sobem app real e fazem 1 round-trip de verdade.

Como rodar:
    uv run pytest api/ -v               # rápidos (~1s)
    uv run pytest api/ -v -m slow       # integração real (~30s+)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_audit_reader, run_graph_callable
from api.server import app
from assistant.audit.reader import AuditReader
from assistant.audit.schema import init_db
from assistant.audit.writer import AuditWriter


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fast_client(monkeypatch):
    """Cliente com lifespan pulado — não carrega o modelo."""
    app.state.skip_warmup = True
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tmp_audit_db(tmp_path, monkeypatch):
    """Audit DB temporário, pré-populado com algumas interações fake."""
    db_path = tmp_path / "audit.db"
    init_db(db_path)
    # Patch AuditReader e AuditWriter pra usar esse path
    monkeypatch.setattr("api.dependencies.AuditReader", lambda: AuditReader(db_path))
    # Reset singleton
    import api.dependencies as deps
    deps._AUDIT_READER_SINGLETON = None
    return db_path


def _fake_state(
    request_id: str = "req-1",
    question: str = "qual o protocolo?",
    patient_id: str | None = None,
    intent: str = "clinica",
    urgency: str = "baixa",
    final_response: str = "Resposta sintética.",
    alerts: list | None = None,
    output_guards: list | None = None,
) -> dict:
    """State minimamente realista pra mockar saída do grafo."""
    return {
        "request_id": request_id,
        "question": question,
        "patient_id": patient_id,
        "intent": intent,
        "urgency": urgency,
        "bypass_detected": False,
        "final_response": final_response,
        "rag_has_sources": True,
        "rag_chunks": [
            {"text": "x", "source_file": "proto.md", "section": "Conduta",
             "score": 0.81, "specialty": ""},
        ],
        "patient_data": None,
        "pending_exams": None,
        "input_guardrails_triggered": [],
        "output_guardrails_triggered": output_guards or [],
        "alerts_emitted": alerts or [],
        "node_trace": [
            {"node": "classify_intent", "timestamp": "x", "latency_s": 0.01,
             "summary": "s", "error": None},
            {"node": "retrieve_protocol", "timestamp": "x", "latency_s": 0.05,
             "summary": "s", "error": None},
            {"node": "generate_response", "timestamp": "x", "latency_s": 0.2,
             "summary": "s", "error": None},
        ],
        "errors": [],
    }


# ────────────────────────────────────────────────────────────────────────
# /health
# ────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_responde_ok_basico(self, fast_client):
        r = fast_client.get("/health")
        assert r.status_code == 200
        j = r.json()
        assert j["version"]
        assert "model_loaded" in j
        assert "db_accessible" in j
        assert "audit_db_accessible" in j


# ────────────────────────────────────────────────────────────────────────
# /patients
# ────────────────────────────────────────────────────────────────────────

class TestPatients:
    def test_lista_pacientes_traz_id_nome_idade(self, fast_client):
        r = fast_client.get("/patients?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            p = data[0]
            assert p["id"].startswith("P")
            assert "nome" in p
            assert "idade" in p

    def test_detalhe_paciente_existente(self, fast_client):
        # P0001 sempre existe no projeto (sintético)
        r = fast_client.get("/patients/P0001")
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == "P0001"
        assert isinstance(d["pending_exams"], list)

    def test_paciente_inexistente_404(self, fast_client):
        r = fast_client.get("/patients/P9999")
        assert r.status_code == 404


# ────────────────────────────────────────────────────────────────────────
# /consult
# ────────────────────────────────────────────────────────────────────────

class TestConsult:
    def test_consult_sem_doctor_id_400(self, fast_client):
        # Override pra evitar carregar grafo
        app.dependency_overrides[run_graph_callable] = lambda: (
            lambda q, p, d: _fake_state()
        )
        try:
            r = fast_client.post("/consult", json={"question": "qual o protocolo?"})
            assert r.status_code == 400
            assert "X-Doctor-Id" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_consult_grafo_mockado_retorna_payload(self, fast_client):
        captured = {}

        def fake_runner(q, p, d):
            captured["question"] = q
            captured["patient_id"] = p
            captured["doctor_id"] = d
            return _fake_state(request_id="abc", question=q, patient_id=p)

        app.dependency_overrides[run_graph_callable] = lambda: fake_runner
        try:
            r = fast_client.post(
                "/consult",
                headers={"X-Doctor-Id": "DR_TEST"},
                json={"question": "qual o protocolo de asma?", "patient_id": "P0001"},
            )
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["request_id"] == "abc"
            assert j["final_response"] == "Resposta sintética."
            assert "explanation" in j
            assert j["was_rewritten"] is False
            assert j["has_alert"] is False
            assert captured["doctor_id"] == "DR_TEST"
            assert captured["patient_id"] == "P0001"
        finally:
            app.dependency_overrides.clear()

    def test_consult_pid_invalido_422(self, fast_client):
        app.dependency_overrides[run_graph_callable] = lambda: (
            lambda q, p, d: _fake_state()
        )
        try:
            r = fast_client.post(
                "/consult",
                headers={"X-Doctor-Id": "DR_TEST"},
                json={"question": "qual?", "patient_id": "X9999"},
            )
            assert r.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_consult_com_alerta_e_rewrite_flags(self, fast_client):
        def runner(q, p, d):
            return _fake_state(
                alerts=[{"timestamp": "t", "patient_id": "P0001",
                         "question": q, "urgency": "alta", "summary": "s"}],
                output_guards=[{
                    "guardrail_name": "prescricao_direta", "triggered": True,
                    "level": "block", "applies_to": "output",
                    "matched_patterns": ["x"], "severity": 0.9,
                    "message": "m", "action_taken": "rewritten",
                }],
                urgency="alta",
            )

        app.dependency_overrides[run_graph_callable] = lambda: runner
        try:
            r = fast_client.post(
                "/consult",
                headers={"X-Doctor-Id": "DR_X"},
                json={"question": "?"},
            )
            j = r.json()
            assert j["has_alert"] is True
            assert j["was_rewritten"] is True
            assert j["urgency"] == "alta"
        finally:
            app.dependency_overrides.clear()


# ────────────────────────────────────────────────────────────────────────
# /audit
# ────────────────────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_list_vazio_quando_db_novo(self, fast_client, tmp_audit_db):
        # Reseta singleton AFTER fixture criou DB temporário
        app.dependency_overrides[get_audit_reader] = lambda: AuditReader(tmp_audit_db)
        try:
            r = fast_client.get("/audit")
            assert r.status_code == 200
            assert r.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_audit_list_com_dados(self, fast_client, tmp_audit_db):
        # Popula 1 interação via writer
        w = AuditWriter(tmp_audit_db)
        state = _fake_state(request_id="r1", patient_id="P0001")
        w.write_interaction(state, latency_ms=1234, doctor_id="DR_X")

        app.dependency_overrides[get_audit_reader] = lambda: AuditReader(tmp_audit_db)
        try:
            r = fast_client.get("/audit?limit=10")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 1
            assert data[0]["request_id"] == "r1"
            assert data[0]["doctor_id"] == "DR_X"
            assert data[0]["patient_id"] == "P0001"
            assert data[0]["has_guardrail"] is False
            assert data[0]["has_alert"] is False
        finally:
            app.dependency_overrides.clear()

    def test_audit_detail_404(self, fast_client, tmp_audit_db):
        app.dependency_overrides[get_audit_reader] = lambda: AuditReader(tmp_audit_db)
        try:
            r = fast_client.get("/audit/inexistente")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_audit_detail_traz_events_e_alerts(self, fast_client, tmp_audit_db):
        w = AuditWriter(tmp_audit_db)
        state = _fake_state(
            request_id="r2", patient_id="P0001",
            output_guards=[{
                "guardrail_name": "prescricao_direta", "triggered": True,
                "level": "block", "applies_to": "output",
                "matched_patterns": ["aa"], "severity": 0.9,
                "message": "m", "action_taken": "rewritten",
            }],
            alerts=[{"timestamp": "t", "patient_id": "P0001",
                     "question": "q", "urgency": "alta", "summary": "s"}],
        )
        w.write_interaction(state, latency_ms=100, doctor_id="DR_Y")

        app.dependency_overrides[get_audit_reader] = lambda: AuditReader(tmp_audit_db)
        try:
            r = fast_client.get("/audit/r2")
            assert r.status_code == 200
            d = r.json()
            assert d["doctor_id"] == "DR_Y"
            assert len(d["guardrail_events"]) == 1
            assert d["guardrail_events"][0]["guardrail_name"] == "prescricao_direta"
            assert len(d["alerts"]) == 1
            assert d["alerts"][0]["urgency"] == "alta"
        finally:
            app.dependency_overrides.clear()

    def test_audit_filter_has_alerts(self, fast_client, tmp_audit_db):
        w = AuditWriter(tmp_audit_db)
        # 1 com alerta, 1 sem
        w.write_interaction(_fake_state(request_id="ra"), latency_ms=1)
        w.write_interaction(
            _fake_state(
                request_id="rb",
                alerts=[{"timestamp": "t", "patient_id": "P0001",
                         "question": "q", "urgency": "alta", "summary": "s"}],
            ),
            latency_ms=1,
        )
        app.dependency_overrides[get_audit_reader] = lambda: AuditReader(tmp_audit_db)
        try:
            r = fast_client.get("/audit?has_alerts=true")
            data = r.json()
            assert len(data) == 1
            assert data[0]["request_id"] == "rb"
            assert data[0]["has_alert"] is True
        finally:
            app.dependency_overrides.clear()


# ────────────────────────────────────────────────────────────────────────
# Migração v1→v2: garante que doctor_id sobrevive numa DB legada
# ────────────────────────────────────────────────────────────────────────

class TestMigration:
    def test_db_sem_doctor_id_recebe_coluna(self, tmp_path):
        db = tmp_path / "legacy.db"
        # Cria DB com schema v1 (sem doctor_id)
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE interactions (
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
                state_snapshot TEXT
            );
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta VALUES ('version', '1');
        """)
        conn.commit()
        conn.close()

        # Rodar init_db → migra
        init_db(db)

        # Verificar coluna existe
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(interactions)").fetchall()}
        version = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()[0]
        conn.close()
        assert "doctor_id" in cols
        assert version == "2"
