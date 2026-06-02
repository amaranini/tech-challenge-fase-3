"""Testes do AuditReader (Fase 6, Bloco 2)."""

from __future__ import annotations

import pytest

from assistant.audit.reader import AuditReader
from assistant.audit.writer import AuditWriter
from assistant.graph_state import initial_state


def _make_state(intent="clinica", patient_id=None, alerts=False,
                guardrails_triggered=None, bypass=False, urgency="baixa"):
    state = initial_state("Pergunta", patient_id=patient_id)
    state["intent"] = intent
    state["urgency"] = urgency
    state["final_response"] = "Resposta"
    state["bypass_detected"] = bypass
    state["output_guardrails_triggered"] = guardrails_triggered or []
    if alerts:
        state["alerts_emitted"] = [{
            "timestamp": "2026-01-01T12:00:00", "patient_id": patient_id,
            "question": "q", "urgency": "alta", "summary": "s",
        }]
    return state


def _gr(name, triggered=True, level="block"):
    return {
        "guardrail_name": name, "triggered": triggered, "level": level,
        "applies_to": "output", "matched_patterns": ["x"],
        "severity": 0.8 if triggered else 0.0, "message": "msg",
        "action_taken": "rewritten" if triggered else None,
    }


@pytest.fixture
def reader_with_data(tmp_path):
    """DB com 5 interações pré-populadas, variando cenário."""
    db_path = tmp_path / "audit.db"
    w = AuditWriter(db_path)
    # 1: normal
    w.write_interaction(_make_state(patient_id="P0001"), latency_ms=100)
    # 2: com guardrail prescricao
    w.write_interaction(_make_state(
        patient_id="P0001",
        guardrails_triggered=[_gr("prescricao_direta")],
    ), latency_ms=200)
    # 3: com alerta
    w.write_interaction(_make_state(
        patient_id="P0002", urgency="alta", alerts=True,
    ), latency_ms=300)
    # 4: bypass
    w.write_interaction(_make_state(
        patient_id=None, intent=None, bypass=True,
    ), latency_ms=50)
    # 5: outro normal
    w.write_interaction(_make_state(patient_id="P0001"), latency_ms=150)
    return AuditReader(db_path)


class TestListRecent:
    def test_lista_em_ordem_descendente(self, reader_with_data):
        rows = reader_with_data.list_recent(10)
        assert len(rows) == 5
        ids = [r.id for r in rows]
        assert ids == sorted(ids, reverse=True)

    def test_respeita_limite(self, reader_with_data):
        rows = reader_with_data.list_recent(2)
        assert len(rows) == 2

    def test_db_inexistente_retorna_vazia(self, tmp_path):
        r = AuditReader(tmp_path / "inexistente.db")
        assert r.list_recent(10) == []


class TestGetById:
    def test_retorna_detalhe_completo(self, reader_with_data):
        rows = reader_with_data.list_recent(10)
        # Pega a interação 2 (com guardrail)
        target = next(r for r in rows if r.id == rows[3].id or r.id == rows[-2].id)
        detail = reader_with_data.get_by_id(target.request_id)
        assert detail is not None
        assert detail.interaction.request_id == target.request_id

    def test_id_inexistente_retorna_none(self, reader_with_data):
        assert reader_with_data.get_by_id("fake-uuid") is None

    def test_get_carrega_guardrail_events(self, reader_with_data):
        # Procura a interação que tem guardrail
        for r in reader_with_data.list_recent(10):
            detail = reader_with_data.get_by_id(r.request_id)
            triggered_count = sum(1 for e in detail.guardrail_events if e.triggered)
            if triggered_count > 0:
                # Encontrou
                e = next(e for e in detail.guardrail_events if e.triggered)
                assert e.guardrail_name == "prescricao_direta"
                assert e.action_taken == "rewritten"
                return
        pytest.fail("Não encontrou interação com guardrail triggered")


class TestFilters:
    def test_filter_by_patient(self, reader_with_data):
        rows = reader_with_data.filter_by_patient("P0001")
        # 3 das 5 interações são de P0001
        assert len(rows) == 3
        assert all(r.patient_id == "P0001" for r in rows)

    def test_filter_by_patient_inexistente(self, reader_with_data):
        rows = reader_with_data.filter_by_patient("P9999")
        assert rows == []

    def test_filter_has_alerts(self, reader_with_data):
        rows = reader_with_data.filter_has_alerts()
        assert len(rows) == 1
        assert rows[0].urgency == "alta"

    def test_filter_has_guardrail(self, reader_with_data):
        rows = reader_with_data.filter_has_guardrail()
        # Só a interação 2 tem guardrail triggered
        assert len(rows) == 1

    def test_filter_by_guardrail_name(self, reader_with_data):
        rows = reader_with_data.filter_by_guardrail("prescricao_direta")
        assert len(rows) == 1

    def test_filter_by_guardrail_nome_inexistente(self, reader_with_data):
        rows = reader_with_data.filter_by_guardrail("nao_existe")
        assert rows == []


class TestStats:
    def test_stats_agregados(self, reader_with_data):
        s = reader_with_data.stats()
        assert s["total_interactions"] == 5
        assert s["with_guardrail_triggered"] == 1
        assert s["with_alert"] == 1
        assert s["bypass_attempts"] == 1
        assert s["avg_latency_ms"] == (100 + 200 + 300 + 50 + 150) // 5

    def test_stats_db_vazio(self, tmp_path):
        r = AuditReader(tmp_path / "vazio.db")
        s = r.stats()
        assert s["total_interactions"] == 0
        assert s["by_intent"] == {}

    def test_stats_por_guardrail(self, reader_with_data):
        s = reader_with_data.stats()
        assert "prescricao_direta" in s["by_guardrail"]
        assert s["by_guardrail"]["prescricao_direta"] == 1


class TestTailSince:
    def test_tail_retorna_so_novas(self, reader_with_data):
        rows = reader_with_data.list_recent(10)
        # last_seen = id do 3º mais recente; tail deve retornar 2
        cursor = rows[2].id
        new = reader_with_data.tail_since(cursor)
        assert len(new) == 2
        assert all(r.id > cursor for r in new)

    def test_tail_em_cursor_atualizado_retorna_vazio(self, reader_with_data):
        rows = reader_with_data.list_recent(1)
        new = reader_with_data.tail_since(rows[0].id)
        assert new == []
