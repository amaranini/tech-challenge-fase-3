"""Testes unitários dos nós do grafo (Fase 5).

Estratégia: mockar LLM e retriever pra rodar rápido (~1s a suíte toda).
Os testes que precisam do modelo real estão em `test_graph_integration.py`
e são marcados `slow`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from assistant.graph_nodes import (
    _PRESCRIPTION_POSOLOGY_PATTERN,
    _PRESCRIPTION_VERB_PATTERN,
    classify_intent,
    emit_alert_if_needed,
    finalize_response,
    guardrail_check,
    make_check_pending_exams_node,
    make_fetch_patient_data_node,
    make_generate_response_node,
    make_retrieve_protocol_node,
    make_rewrite_node,
    make_triage_urgency_node,
    refuse_node,
)
from assistant.graph_state import initial_state
from assistant.intent_classifier import classify_intent_rules
from assistant.tools.patient_records import PatientRecord


# ────────────────────────────────────────────────────────────────────────
# Nó 1 — classify_intent (determinístico)
# ────────────────────────────────────────────────────────────────────────

class TestClassifyIntent:
    def test_clinica(self):
        state = initial_state("Qual o protocolo para crise asmática?")
        out = classify_intent(state)
        assert out["intent"] == "clinica"
        assert len(out["node_trace"]) == 1
        assert "asmática" in out["node_trace"][0]["summary"].lower() or \
               "kw=" in out["node_trace"][0]["summary"]

    def test_administrativa(self):
        state = initial_state("Que horas começa o plantão?")
        out = classify_intent(state)
        assert out["intent"] == "administrativa"

    def test_fora_de_escopo(self):
        state = initial_state("Me ensina a fazer bolo de chocolate")
        out = classify_intent(state)
        assert out["intent"] == "fora_de_escopo"

    def test_kw_match_ordem_admin_antes_medico(self):
        # "plantão da emergência" — plantão (admin) deve vencer porque admin é checado antes
        state = initial_state("Que horas começa o plantão da emergência amanhã?")
        out = classify_intent(state)
        assert out["intent"] == "administrativa"


# ────────────────────────────────────────────────────────────────────────
# Nó 2 — triage_urgency (com LLM mockado)
# ────────────────────────────────────────────────────────────────────────

class TestTriageUrgency:
    def _mock_llm(self, response_text: str) -> MagicMock:
        m = MagicMock()
        resp = MagicMock()
        resp.content = response_text
        m.invoke.return_value = resp
        return m

    def test_alta(self):
        llm = self._mock_llm("alta")
        node = make_triage_urgency_node(llm)
        out = node(initial_state("Paciente em sepse grave"))
        assert out["urgency"] == "alta"

    def test_media_parsing_tolerante(self):
        # LLM cuspiu output com formatação extra
        llm = self._mock_llm("Resposta: media.")
        node = make_triage_urgency_node(llm)
        out = node(initial_state("Paciente com febre 39"))
        assert out["urgency"] == "media"

    def test_parsing_falhou_usa_fallback(self):
        llm = self._mock_llm("xyz blah blah")
        node = make_triage_urgency_node(llm)
        out = node(initial_state("Pergunta qualquer"))
        assert out["urgency"] == "media"  # fallback seguro
        assert out["errors"]  # erro registrado mas grafo continua

    def test_excecao_nao_propaga(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("modelo morreu")
        node = make_triage_urgency_node(llm)
        out = node(initial_state("..."))
        assert out["urgency"] == "media"
        assert "modelo morreu" in out["errors"][0]


# ────────────────────────────────────────────────────────────────────────
# Nó 3 — fetch_patient_data
# ────────────────────────────────────────────────────────────────────────

class TestFetchPatientData:
    def test_skip_sem_id(self):
        lookup = MagicMock()
        node = make_fetch_patient_data_node(patient_lookup=lookup)
        state = initial_state("Pergunta sem ID")
        out = node(state)
        assert "patient_data" not in out
        lookup.assert_not_called()
        assert "skip" in out["node_trace"][0]["summary"]

    def test_id_via_argumento(self):
        rec = PatientRecord(id="P0001", nome="Ana", idade=30, sexo="F",
                            alergias="", medicacoes_atuais="",
                            historico_resumido="hist")
        lookup = MagicMock(return_value=rec)
        node = make_fetch_patient_data_node(patient_lookup=lookup)
        state = initial_state("Pergunta", patient_id="P0001")
        out = node(state)
        assert out["patient_data"]["id"] == "P0001"
        lookup.assert_called_once_with("P0001")

    def test_id_via_regex_da_pergunta(self):
        rec = PatientRecord(id="P0042", nome="X", idade=20, sexo="M",
                            alergias="", medicacoes_atuais="",
                            historico_resumido="")
        lookup = MagicMock(return_value=rec)
        node = make_fetch_patient_data_node(patient_lookup=lookup)
        state = initial_state("Para o paciente P0042, qual conduta?")
        out = node(state)
        assert out["patient_id"] == "P0042"
        assert out["patient_data"]["id"] == "P0042"

    def test_id_nao_encontrado_registra_erro_mas_continua(self):
        lookup = MagicMock(return_value=None)
        node = make_fetch_patient_data_node(patient_lookup=lookup)
        state = initial_state("Conduta para P9999")
        out = node(state)
        assert out["patient_id"] == "P9999"
        assert out["patient_data"] is None
        assert any("P9999" in e for e in out["errors"])

    def test_excecao_no_lookup_nao_propaga(self):
        lookup = MagicMock(side_effect=RuntimeError("DB morreu"))
        node = make_fetch_patient_data_node(patient_lookup=lookup)
        out = node(initial_state("Pergunta P0001"))
        assert "DB morreu" in out["errors"][0]


# ────────────────────────────────────────────────────────────────────────
# Nó 4 — check_pending_exams
# ────────────────────────────────────────────────────────────────────────

class TestCheckPendingExams:
    def test_skip_sem_id(self):
        lookup = MagicMock()
        node = make_check_pending_exams_node(pending_exams_lookup=lookup)
        out = node(initial_state("Pergunta"))
        assert "pending_exams" not in out
        lookup.assert_not_called()

    def test_lista_vazia_quando_paciente_sem_exames(self):
        lookup = MagicMock(return_value=[])
        node = make_check_pending_exams_node(pending_exams_lookup=lookup)
        out = node(initial_state("Pergunta", patient_id="P0001"))
        assert out["pending_exams"] == []

    def test_retorna_exames(self):
        exams = [
            {"tipo_exame": "ECG", "data_solicitacao": "2026-05-01", "prioridade": "urgente"},
        ]
        lookup = MagicMock(return_value=exams)
        node = make_check_pending_exams_node(pending_exams_lookup=lookup)
        out = node(initial_state("...", patient_id="P0002"))
        assert out["pending_exams"] == exams

    def test_excecao_nao_propaga(self):
        lookup = MagicMock(side_effect=RuntimeError("oops"))
        node = make_check_pending_exams_node(pending_exams_lookup=lookup)
        out = node(initial_state("...", patient_id="P0001"))
        assert out["pending_exams"] == []
        assert out["errors"]


# ────────────────────────────────────────────────────────────────────────
# Nó 5 — retrieve_protocol
# ────────────────────────────────────────────────────────────────────────

class TestRetrieveProtocol:
    def _mock_chunk(self, text="abc", score=0.8, source="x.md", section="Indicação"):
        from assistant.rag.retriever import RetrievedChunk
        return RetrievedChunk(
            text=text,
            metadata={"source_file": source, "section": section, "title": "T", "specialty": ""},
            score=score,
        )

    def test_chunks_retornam_no_state(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self._mock_chunk()]
        node = make_retrieve_protocol_node(retriever)
        out = node(initial_state("Asma"))
        assert out["rag_has_sources"] is True
        assert len(out["rag_chunks"]) == 1

    def test_sem_chunks_seta_flag_false(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        node = make_retrieve_protocol_node(retriever)
        out = node(initial_state("blah"))
        assert out["rag_has_sources"] is False
        assert out["rag_chunks"] == []

    def test_excecao_nao_propaga(self):
        retriever = MagicMock()
        retriever.retrieve.side_effect = RuntimeError("chroma morreu")
        node = make_retrieve_protocol_node(retriever)
        out = node(initial_state("..."))
        assert out["rag_has_sources"] is False
        assert out["errors"]


# ────────────────────────────────────────────────────────────────────────
# Nó 6 — generate_response (mock do LLM)
# ────────────────────────────────────────────────────────────────────────

class TestGenerateResponse:
    def _mock_llm(self, response_text: str) -> MagicMock:
        m = MagicMock()
        resp = MagicMock()
        resp.content = response_text
        m.invoke.return_value = resp
        return m

    def test_resposta_basica(self):
        llm = self._mock_llm("Resposta clínica.")
        node = make_generate_response_node(llm)
        out = node(initial_state("Asma"))
        assert out["draft_response"] == "Resposta clínica."

    def test_excecao_devolve_fallback(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("modelo morreu")
        node = make_generate_response_node(llm)
        out = node(initial_state("..."))
        assert "Não foi possível gerar" in out["draft_response"]
        assert out["errors"]


# ────────────────────────────────────────────────────────────────────────
# Nó 7 — guardrail_check
# ────────────────────────────────────────────────────────────────────────

class TestGuardrailCheck:
    def test_detecta_prescricao(self):
        state = initial_state("?")
        state["draft_response"] = "Prescrevo amoxicilina 500mg de 8/8h."
        out = guardrail_check(state)
        assert out["guardrail_flags"]
        assert "prescription_with_dose" in out["guardrail_flags"][0]

    def test_nao_detecta_dose_de_referencia(self):
        state = initial_state("?")
        state["draft_response"] = "A dose de referência é 500mg, a prescrição é decisão do médico."
        out = guardrail_check(state)
        assert out["guardrail_flags"] == []

    def test_padroes_variados_da_regex(self):
        # Ordem clássica: verbo + droga + dose
        assert _PRESCRIPTION_VERB_PATTERN.search("Recomendo paracetamol 1 g via oral")
        assert _PRESCRIPTION_VERB_PATTERN.search("administre dipirona 1g")
        # Ordem invertida: verbo + dose + droga (caso real do eval 9)
        assert _PRESCRIPTION_VERB_PATTERN.search("Prescreva 500mg de amoxicilina")
        assert _PRESCRIPTION_VERB_PATTERN.search("Recomendo 1g de paracetamol")
        # Não dispara em texto comum
        assert not _PRESCRIPTION_VERB_PATTERN.search("Tome 2 comprimidos por dia")

    def test_detecta_posologia_sem_verbo(self):
        # Padrão 2: droga + dose + "a cada Xh" (caso real da eval #9)
        state = initial_state("?")
        state["draft_response"] = "Amoxicilina 500mg a cada 8 horas."
        out = guardrail_check(state)
        assert out["guardrail_flags"]
        assert "prescription_posology" in out["guardrail_flags"][0]

    def test_posologia_pattern_nao_pega_dose_de_referencia(self):
        # "A dose de referência é 500mg" — sem posologia, sem verbo → ok
        state = initial_state("?")
        state["draft_response"] = "A dose de referência é 500mg, prescrição decisão do médico."
        out = guardrail_check(state)
        assert out["guardrail_flags"] == []


# ────────────────────────────────────────────────────────────────────────
# Nó 8 — emit_alert_if_needed
# ────────────────────────────────────────────────────────────────────────

class TestEmitAlert:
    def test_no_op_quando_urgencia_baixa(self, tmp_path, monkeypatch):
        # Redireciona o log pra tmp pra não poluir
        from assistant import graph_nodes
        monkeypatch.setattr(graph_nodes, "ALERTS_LOG_PATH", tmp_path / "alerts.jsonl")
        state = initial_state("?")
        state["urgency"] = "baixa"
        out = emit_alert_if_needed(state)
        assert "alerts_emitted" not in out
        assert not (tmp_path / "alerts.jsonl").exists()

    def test_emite_quando_alta(self, tmp_path, monkeypatch, capsys):
        from assistant import graph_nodes
        monkeypatch.setattr(graph_nodes, "ALERTS_LOG_PATH", tmp_path / "alerts.jsonl")
        state = initial_state("Emergência", patient_id="P0001")
        state["urgency"] = "alta"
        state["draft_response"] = "Conduta imediata: oxigênio, monitorização."
        out = emit_alert_if_needed(state)
        assert len(out["alerts_emitted"]) == 1
        assert out["alerts_emitted"][0]["urgency"] == "alta"
        assert (tmp_path / "alerts.jsonl").exists()
        captured = capsys.readouterr()
        assert "ALERTA EMITIDO" in captured.out


# ────────────────────────────────────────────────────────────────────────
# Nó 9 — finalize_response
# ────────────────────────────────────────────────────────────────────────

class TestFinalizeResponse:
    def test_inclui_disclaimer(self):
        state = initial_state("?")
        state["draft_response"] = "Conduta X é apropriada."
        out = finalize_response(state)
        assert "conduta final cabe" in out["final_response"].lower()

    def test_inclui_fontes_se_rag(self):
        state = initial_state("?")
        state["draft_response"] = "Resposta."
        state["rag_has_sources"] = True
        state["rag_chunks"] = [
            {"source_file": "proto.md", "section": "Indicação", "score": 0.81},
        ]
        out = finalize_response(state)
        assert "Fontes consultadas" in out["final_response"]
        assert "proto.md" in out["final_response"]

    def test_inclui_aviso_alerta_se_alta(self):
        state = initial_state("?")
        state["draft_response"] = "Conduta."
        state["alerts_emitted"] = [
            {"timestamp": "x", "patient_id": "P1", "question": "q",
             "urgency": "alta", "summary": "s"}
        ]
        out = finalize_response(state)
        assert "🚨" in out["final_response"]
        assert "urgência alta" in out["final_response"]

    def test_nao_duplica_disclaimer(self):
        state = initial_state("?")
        state["draft_response"] = (
            "Resposta. Esta orientação é apoio à decisão; a conduta final "
            "cabe ao médico assistente."
        )
        out = finalize_response(state)
        # Deve aparecer só 1 vez (não acrescentou outra)
        assert out["final_response"].lower().count("conduta final cabe") == 1


# ────────────────────────────────────────────────────────────────────────
# Nó refuse
# ────────────────────────────────────────────────────────────────────────

class TestRefuseNode:
    def test_gera_template_fixo(self):
        out = refuse_node(initial_state("Me ensina bolo"))
        assert "fora do escopo" in out["draft_response"]
        assert "bolo" in out["draft_response"]


# ────────────────────────────────────────────────────────────────────────
# Nó rewrite (com LLM mockado)
# ────────────────────────────────────────────────────────────────────────

class TestRewriteNode:
    def test_substitui_draft_e_marca_was_rewritten(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = "Versão reescrita sem dose."
        llm.invoke.return_value = resp
        node = make_rewrite_node(llm)
        state = initial_state("?")
        state["draft_response"] = "Prescrevo amoxicilina 500mg."
        state["guardrail_flags"] = ["prescription_with_dose:Prescrevo amoxicilina 500mg"]
        out = node(state)
        assert out["draft_response"] == "Versão reescrita sem dose."
        assert out["was_rewritten"] is True

    def test_excecao_nao_propaga(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("morreu")
        node = make_rewrite_node(llm)
        state = initial_state("?")
        state["draft_response"] = "draft"
        out = node(state)
        assert out["errors"]


# ────────────────────────────────────────────────────────────────────────
# Sanity tests do classifier_rules (Nó 1 backend)
# ────────────────────────────────────────────────────────────────────────

class TestIntentClassifierRules:
    @pytest.mark.parametrize("question,expected", [
        ("Qual o protocolo para sepse?", "clinica"),
        ("Que horas começa o plantão?", "administrativa"),
        ("Me indica um filme bom pra ver", "fora_de_escopo"),
        ("Paciente P0001 com taquicardia", "clinica"),
        ("Fechamento do livro do plantão", "administrativa"),
        ("Viagem pra Buenos Aires", "fora_de_escopo"),
    ])
    def test_classifica_corretamente(self, question, expected):
        intent, _ = classify_intent_rules(question)
        assert intent == expected
