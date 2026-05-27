"""Testes de integração end-to-end do grafo (Fase 5).

Carregam o MedicalLLM real (lento) + retriever real (Chroma) + DB real.
Marcados `slow` — só rodam com `-m slow` ou em CI dedicada.

Pré-requisitos:
- Banco construído: `uv run python assistant/tools/build_patient_db.py`
- Índice RAG construído: `uv run python assistant/rag/build_index.py`
- Adapter LoRA: `finetuning/output/adapters/` (Fase 2)

Rodar:
    uv run pytest assistant/test_graph_integration.py -v -m slow -s
"""

from __future__ import annotations

import pytest

from assistant.graph import run_medical_graph


@pytest.fixture(scope="module")
def _warm_graph():
    """Compila o grafo uma vez antes dos testes (carrega modelo + RAG)."""
    from assistant.graph import _get_graph
    _get_graph()
    yield


@pytest.mark.slow
class TestGraphIntegration:
    """3 testes end-to-end cobrindo os 3 caminhos principais do grafo."""

    def test_fluxo_normal_clinico(self, _warm_graph):
        """Pergunta clínica simples → todos os nós principais executam."""
        state = run_medical_graph("Qual o protocolo para crise asmática?")
        assert state["intent"] == "clinica"
        # Caminho clínico: trace tem 9 nós, sem refuse e sem rewrite
        nodes = [t["node"] for t in state["node_trace"]]
        assert "refuse_node" not in nodes
        assert "rewrite_node" not in nodes
        assert "classify_intent" in nodes
        assert "triage_urgency" in nodes
        assert "retrieve_protocol" in nodes
        assert "generate_response" in nodes
        assert "guardrail_check" in nodes
        assert "finalize_response" in nodes
        assert state["final_response"]
        # Disclaimer deve estar na resposta final
        assert "conduta final cabe" in state["final_response"].lower()

    def test_fluxo_refuse(self, _warm_graph):
        """Pergunta fora de escopo → refuse_node curto-circuita o caminho."""
        state = run_medical_graph("Me ensina a fazer bolo de chocolate")
        assert state["intent"] == "fora_de_escopo"
        nodes = [t["node"] for t in state["node_trace"]]
        assert "refuse_node" in nodes
        # Não passa pelos nós médicos
        assert "retrieve_protocol" not in nodes
        assert "generate_response" not in nodes
        # Mas chega ao finalize
        assert "finalize_response" in nodes
        assert state["final_response"]
        assert "fora do escopo" in state["final_response"].lower()

    def test_alerta_urgencia_alta(self, _warm_graph):
        """Caso de urgência alta → alerta deve ser emitido."""
        state = run_medical_graph(
            "Paciente em parada cardiorrespiratória, qual a sequência de RCP?"
        )
        assert state["intent"] == "clinica"
        assert state["urgency"] == "alta"
        # Alerta foi emitido
        assert state["alerts_emitted"]
        assert state["alerts_emitted"][0]["urgency"] == "alta"
        # Resposta final menciona o alerta
        assert "🚨" in state["final_response"] or \
               "urgência alta" in state["final_response"].lower()
