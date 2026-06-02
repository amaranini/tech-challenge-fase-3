"""Testes unitários da explainability (Fase 6, Bloco 3).

Função pura sobre o state — testes sem LLM, sem mocks, rápidos.
"""

from __future__ import annotations

from assistant.explainability import build_explanation, format_explanation
from assistant.graph_state import initial_state


def _make_state(**overrides):
    s = initial_state("Pergunta", patient_id=overrides.pop("patient_id", None))
    for k, v in overrides.items():
        s[k] = v
    return s


# ────────────────────────────────────────────────────────────────────────
# Estrutura básica
# ────────────────────────────────────────────────────────────────────────

class TestBasicStructure:
    def test_chaves_obrigatorias_presentes(self):
        state = _make_state(intent="clinica", urgency="baixa")
        exp = build_explanation(state)
        for key in (
            "request_id", "classification", "patient_used", "exams_consulted",
            "sources", "no_sources_reason", "guardrails_triggered",
            "alerts_emitted", "model_info", "latency_breakdown_s", "errors",
        ):
            assert key in exp, f"chave ausente: {key}"

    def test_classification_extraida(self):
        state = _make_state(intent="clinica", urgency="alta",
                            bypass_detected=False)
        exp = build_explanation(state)
        assert exp["classification"]["intent"] == "clinica"
        assert exp["classification"]["urgency"] == "alta"
        assert exp["classification"]["bypass_detected"] is False

    def test_request_id_preserved(self):
        state = _make_state(request_id="abc-123")
        exp = build_explanation(state)
        assert exp["request_id"] == "abc-123"


# ────────────────────────────────────────────────────────────────────────
# Paciente
# ────────────────────────────────────────────────────────────────────────

class TestPatient:
    def test_sem_paciente_vira_none(self):
        exp = build_explanation(_make_state())
        assert exp["patient_used"] is None

    def test_lista_campos_consultados_nao_vazios(self):
        state = _make_state(patient_data={
            "id": "P0001", "nome": "Ana", "idade": 30, "sexo": "F",
            "alergias": "Nenhuma",
            "medicacoes_atuais": "",  # vazio → não conta
            "historico_resumido": "Hist",
        })
        exp = build_explanation(state)
        p = exp["patient_used"]
        assert p["id"] == "P0001"
        assert set(p["fields_consulted"]) == {
            "nome", "idade", "sexo", "alergias", "historico_resumido",
        }
        # medicacoes_atuais ficou vazio → não está
        assert "medicacoes_atuais" not in p["fields_consulted"]


# ────────────────────────────────────────────────────────────────────────
# Exames
# ────────────────────────────────────────────────────────────────────────

class TestExams:
    def test_sem_exames_vira_none(self):
        exp = build_explanation(_make_state())
        assert exp["exams_consulted"] is None

    def test_lista_vazia_tambem_vira_none(self):
        exp = build_explanation(_make_state(pending_exams=[]))
        assert exp["exams_consulted"] is None

    def test_com_exames_lista_campos_essenciais(self):
        exams = [
            {"tipo_exame": "ECG", "data_solicitacao": "2026-05-01",
             "prioridade": "urgente"},
        ]
        exp = build_explanation(_make_state(pending_exams=exams))
        assert exp["exams_consulted"] == exams


# ────────────────────────────────────────────────────────────────────────
# Fontes RAG e no_sources_reason
# ────────────────────────────────────────────────────────────────────────

class TestSources:
    def test_com_chunks_lista_fonte(self):
        chunks = [{
            "text": "x", "source_file": "proto.md", "section": "Conduta",
            "score": 0.81, "specialty": "",
        }]
        state = _make_state(
            rag_chunks=chunks, rag_has_sources=True,
            node_trace=[{"node": "retrieve_protocol", "timestamp": "x",
                         "latency_s": 0.1, "summary": "s", "error": None}],
        )
        exp = build_explanation(state)
        assert len(exp["sources"]) == 1
        assert exp["sources"][0]["file"] == "proto.md"
        assert exp["sources"][0]["section"] == "Conduta"
        assert exp["no_sources_reason"] is None

    def test_sem_chunks_mas_rag_rodou(self):
        state = _make_state(
            rag_chunks=[], rag_has_sources=False,
            node_trace=[{"node": "retrieve_protocol", "timestamp": "x",
                         "latency_s": 0.1, "summary": "s", "error": None}],
        )
        exp = build_explanation(state)
        assert exp["sources"] == []
        assert exp["no_sources_reason"]
        assert "threshold" in exp["no_sources_reason"]

    def test_rag_nem_rodou(self):
        state = _make_state(
            rag_chunks=None, rag_has_sources=False,
            node_trace=[{"node": "refuse_node", "timestamp": "x",
                         "latency_s": 0.0, "summary": "s", "error": None}],
        )
        exp = build_explanation(state)
        assert exp["sources"] == []
        assert "refuse" in exp["no_sources_reason"].lower() or \
               "bypass" in exp["no_sources_reason"].lower()


# ────────────────────────────────────────────────────────────────────────
# Guardrails
# ────────────────────────────────────────────────────────────────────────

class TestGuardrails:
    def test_so_pega_triggered(self):
        state = _make_state(
            output_guardrails_triggered=[
                {"guardrail_name": "prescricao_direta", "triggered": True,
                 "level": "block", "applies_to": "output",
                 "matched_patterns": ["foo"], "severity": 0.9,
                 "message": "x", "action_taken": "rewritten"},
                {"guardrail_name": "diagnostico_definitivo", "triggered": False,
                 "level": "block", "applies_to": "output",
                 "matched_patterns": [], "severity": 0.0, "message": "",
                 "action_taken": None},
            ],
        )
        exp = build_explanation(state)
        assert len(exp["guardrails_triggered"]) == 1
        assert exp["guardrails_triggered"][0]["name"] == "prescricao_direta"
        assert exp["guardrails_triggered"][0]["action_taken"] == "rewritten"

    def test_combina_input_e_output(self):
        state = _make_state(
            input_guardrails_triggered=[{
                "guardrail_name": "bypass_attempt", "triggered": True,
                "level": "block", "applies_to": "input",
                "matched_patterns": ["x"], "severity": 1.0, "message": "y",
                "action_taken": None,
            }],
            output_guardrails_triggered=[{
                "guardrail_name": "prescricao_direta", "triggered": True,
                "level": "block", "applies_to": "output",
                "matched_patterns": ["z"], "severity": 0.9, "message": "w",
                "action_taken": "rewritten",
            }],
        )
        exp = build_explanation(state)
        names = {g["name"] for g in exp["guardrails_triggered"]}
        assert names == {"bypass_attempt", "prescricao_direta"}

    def test_was_rewritten_true_quando_ha_rewrite(self):
        state = _make_state(output_guardrails_triggered=[{
            "guardrail_name": "x", "triggered": True, "level": "block",
            "applies_to": "output", "matched_patterns": [],
            "severity": 0.5, "message": "", "action_taken": "rewritten",
        }])
        exp = build_explanation(state)
        assert exp["was_rewritten"] is True

    def test_was_rewritten_false_quando_nao(self):
        exp = build_explanation(_make_state())
        assert exp["was_rewritten"] is False


# ────────────────────────────────────────────────────────────────────────
# Alertas, modelo, latências
# ────────────────────────────────────────────────────────────────────────

class TestAlertsModelLatency:
    def test_alerts_serializados(self):
        state = _make_state(alerts_emitted=[{
            "timestamp": "2026-01-01", "patient_id": "P0001",
            "question": "q", "urgency": "alta", "summary": "s",
        }])
        exp = build_explanation(state)
        assert len(exp["alerts_emitted"]) == 1
        assert exp["alerts_emitted"][0]["urgency"] == "alta"

    def test_model_info_tem_base_e_adapter(self):
        exp = build_explanation(_make_state())
        m = exp["model_info"]
        assert "base" in m
        assert "adapter" in m

    def test_latency_breakdown_soma_total(self):
        state = _make_state(node_trace=[
            {"node": "a", "timestamp": "x", "latency_s": 0.5,
             "summary": "s", "error": None},
            {"node": "b", "timestamp": "x", "latency_s": 0.3,
             "summary": "s", "error": None},
        ])
        exp = build_explanation(state)
        assert exp["latency_breakdown_s"] == {"a": 0.5, "b": 0.3}
        assert exp["total_latency_s"] == 0.8


# ────────────────────────────────────────────────────────────────────────
# Format / render (smoke)
# ────────────────────────────────────────────────────────────────────────

class TestFormatExplanation:
    def test_format_basico_nao_quebra(self):
        from rich.console import Console
        exp = build_explanation(_make_state(
            intent="clinica", urgency="baixa",
            patient_data={"id": "P0001", "nome": "x", "idade": 30,
                          "sexo": "M", "alergias": "", "medicacoes_atuais": "",
                          "historico_resumido": "h"},
        ))
        rendered = format_explanation(exp, detail=False)
        # Captura num console em memória
        c = Console(record=True, width=120)
        c.print(rendered)
        out = c.export_text()
        assert "request_id" in out
        assert "Classificação" in out
        assert "Paciente" in out
        assert "Fontes RAG" in out
        assert "Guardrails" in out

    def test_format_detail_inclui_latencias_e_modelo(self):
        from rich.console import Console
        exp = build_explanation(_make_state(
            node_trace=[{"node": "x", "timestamp": "t",
                         "latency_s": 0.5, "summary": "s", "error": None}],
        ))
        rendered = format_explanation(exp, detail=True)
        c = Console(record=True, width=120)
        c.print(rendered)
        out = c.export_text()
        assert "Latências" in out
        assert "Modelo" in out
