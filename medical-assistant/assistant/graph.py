"""Grafo LangGraph principal do assistente clínico (Fase 5).

Substitui o orquestrador da Fase 4 (`assistant/chain.py`) por um grafo de
estado explícito com 9 nós + 2 auxiliares (refuse, rewrite). A chain antiga
continua existindo como referência da Fase 4.

Interface pública:
    build_graph(...)         → CompiledGraph (LangGraph)
    run_medical_graph(...)   → MedicalState completo após execução
    export_diagram(out_dir)  → salva Mermaid (.md) e tenta PNG

Rodar como módulo: `uv run python assistant/graph.py` exporta o diagrama e
faz um smoke test com 1 query.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from assistant.config import RAG_MIN_SCORE
from assistant.graph_nodes import (
    classify_intent,
    emit_alert_if_needed,
    finalize_response,
    guardrail_check,
    input_guardrail_check,
    make_check_pending_exams_node,
    make_fetch_patient_data_node,
    make_generate_response_node,
    make_retrieve_protocol_node,
    make_rewrite_node,
    make_triage_urgency_node,
    refuse_node,
)
from assistant.graph_state import MedicalState, initial_state

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRACES_LOG_PATH = _PROJECT_ROOT / "logging_" / "graph_traces.jsonl"


# ────────────────────────────────────────────────────────────────────────
# Roteamento condicional
# ────────────────────────────────────────────────────────────────────────

def _route_after_input_guardrail(state: MedicalState) -> str:
    """De input_guardrail_check (Nó 0, Fase 6): bypass → refuse; senão → classify."""
    if state.get("bypass_detected"):
        return "refuse_node"
    return "classify_intent"


def _route_after_intent(state: MedicalState) -> str:
    """De classify_intent: fora_de_escopo → refuse; senão → triage."""
    if state.get("intent") == "fora_de_escopo":
        return "refuse_node"
    return "triage_urgency"


def _route_after_guardrail(state: MedicalState) -> str:
    """De guardrail_check: algum BLOCK triggered → rewrite; senão → emit_alert.

    Atualizado na Fase 6: agora olha `output_guardrails_triggered`, não o
    antigo `guardrail_flags` (que foi removido).
    """
    results = state.get("output_guardrails_triggered") or []
    if any(r.get("triggered") and r.get("level") == "block" for r in results):
        return "rewrite_node"
    return "emit_alert_if_needed"


# ────────────────────────────────────────────────────────────────────────
# Construção do grafo
# ────────────────────────────────────────────────────────────────────────

def build_graph(
    llm: Optional[BaseChatModel] = None,
    classifier_llm: Optional[BaseChatModel] = None,
    retriever: Optional[Any] = None,
    patient_lookup: Optional[Callable] = None,
    pending_exams_lookup: Optional[Callable] = None,
    top_k: int = 3,
    min_score: float = RAG_MIN_SCORE,
):
    """Monta o StateGraph com 9 nós + 2 auxiliares.

    Parâmetros opcionais permitem injeção pra testes (mock do LLM, retriever
    fake, etc). Quando None, usa os defaults do projeto (build_default_llm,
    ProtocolRetriever, get_patient_by_id, get_pending_exams).
    """
    # Lazy imports pra permitir uso em testes sem carregar modelo
    if llm is None or classifier_llm is None:
        from assistant.llm import build_default_llm
    if llm is None:
        llm = build_default_llm()
    if classifier_llm is None:
        # Instância separada com temperatura 0 pro Nó 2 — system explicitamente
        # passado pelo nó, então system_prompt da instância fica None
        from assistant.config import ADAPTER_PATH, MODEL_PATH
        from assistant.llm import MedicalLLM
        classifier_llm = MedicalLLM(
            model_path=MODEL_PATH,
            adapter_path=ADAPTER_PATH,
            system_prompt=None,
            temperature=0.0,
            max_tokens=16,
            top_p=1.0,
        )
    if retriever is None:
        from assistant.rag.retriever import ProtocolRetriever
        retriever = ProtocolRetriever()

    # Constrói nós-fábrica
    triage_node = make_triage_urgency_node(classifier_llm)
    fetch_node = make_fetch_patient_data_node(
        patient_lookup if patient_lookup else None  # default no factory
    ) if patient_lookup else make_fetch_patient_data_node()
    exams_node = make_check_pending_exams_node(
        pending_exams_lookup
    ) if pending_exams_lookup else make_check_pending_exams_node()
    rag_node = make_retrieve_protocol_node(retriever, top_k=top_k, min_score=min_score)
    generate_node = make_generate_response_node(llm)
    rewrite_n = make_rewrite_node(llm)

    g: StateGraph = StateGraph(MedicalState)

    # ─── Nós ─────────────────────────────────────────────────────────────
    g.add_node("input_guardrail_check", input_guardrail_check)  # Nó 0 (Fase 6)
    g.add_node("classify_intent", classify_intent)
    g.add_node("triage_urgency", triage_node)
    g.add_node("fetch_patient_data", fetch_node)
    g.add_node("check_pending_exams", exams_node)
    g.add_node("retrieve_protocol", rag_node)
    g.add_node("generate_response", generate_node)
    g.add_node("guardrail_check", guardrail_check)
    g.add_node("emit_alert_if_needed", emit_alert_if_needed)
    g.add_node("finalize_response", finalize_response)
    g.add_node("refuse_node", refuse_node)
    g.add_node("rewrite_node", rewrite_n)

    # ─── Entry ──────────────────────────────────────────────────────────
    g.add_edge(START, "input_guardrail_check")

    # ─── Roteamento 0 (Fase 6): bypass → refuse curto-circuita o grafo ─
    g.add_conditional_edges(
        "input_guardrail_check",
        _route_after_input_guardrail,
        {
            "refuse_node": "refuse_node",
            "classify_intent": "classify_intent",
        },
    )

    # ─── Roteamento 1: classify_intent → refuse OU triage ──────────────
    g.add_conditional_edges(
        "classify_intent",
        _route_after_intent,
        {
            "refuse_node": "refuse_node",
            "triage_urgency": "triage_urgency",
        },
    )

    # ─── Caminho clínico principal ──────────────────────────────────────
    g.add_edge("triage_urgency", "fetch_patient_data")
    g.add_edge("fetch_patient_data", "check_pending_exams")
    g.add_edge("check_pending_exams", "retrieve_protocol")
    g.add_edge("retrieve_protocol", "generate_response")
    g.add_edge("generate_response", "guardrail_check")

    # ─── Roteamento 2: guardrail → rewrite OU emit_alert ───────────────
    g.add_conditional_edges(
        "guardrail_check",
        _route_after_guardrail,
        {
            "rewrite_node": "rewrite_node",
            "emit_alert_if_needed": "emit_alert_if_needed",
        },
    )

    # ─── Convergência: rewrite e emit_alert vão pra finalize ───────────
    g.add_edge("rewrite_node", "emit_alert_if_needed")
    g.add_edge("emit_alert_if_needed", "finalize_response")

    # ─── Refuse short-circuit ─────────────────────────────────────────
    g.add_edge("refuse_node", "finalize_response")

    # ─── End ───────────────────────────────────────────────────────────
    g.add_edge("finalize_response", END)

    return g.compile()


# ────────────────────────────────────────────────────────────────────────
# Interface pública: run_medical_graph
# ────────────────────────────────────────────────────────────────────────

_GRAPH_SINGLETON = None


def _get_graph():
    global _GRAPH_SINGLETON
    if _GRAPH_SINGLETON is None:
        _GRAPH_SINGLETON = build_graph()
    return _GRAPH_SINGLETON


def _ensure_traces_log() -> None:
    TRACES_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def run_medical_graph(
    question: str,
    patient_id: Optional[str] = None,
) -> MedicalState:
    """Roda o grafo numa pergunta e devolve o State final.

    Lazy-build do grafo (singleton de módulo). Grava trace estruturado em
    logging_/graph_traces.jsonl (1 linha por execução completa).
    """
    graph = _get_graph()
    state_in = initial_state(question=question, patient_id=patient_id)
    t0 = time.monotonic()
    state_out = graph.invoke(state_in)
    total = time.monotonic() - t0
    logger.info("Grafo executado em %.2fs (%d nós no trace)",
                total, len(state_out.get("node_trace", [])))

    # Persistência do trace
    try:
        _ensure_traces_log()
        # Serializar tudo, mas alguns objetos podem não ser JSON-friendly
        # Fase 6: trocou guardrail_flags/was_rewritten por listas estruturadas
        output_guardrails = state_out.get("output_guardrails_triggered") or []
        was_rewritten = any(
            r.get("action_taken") == "rewritten"
            for r in output_guardrails
        )
        log_entry = {
            "ts": state_out.get("node_trace", [{}])[-1].get("timestamp"),
            "request_id": state_out.get("request_id"),
            "question": question,
            "patient_id": state_out.get("patient_id"),
            "intent": state_out.get("intent"),
            "urgency": state_out.get("urgency"),
            "rag_has_sources": state_out.get("rag_has_sources"),
            "bypass_detected": state_out.get("bypass_detected"),
            "input_guardrails_triggered": [
                r for r in (state_out.get("input_guardrails_triggered") or [])
                if r.get("triggered")
            ],
            "output_guardrails_triggered": [
                r for r in output_guardrails if r.get("triggered")
            ],
            "was_rewritten": was_rewritten,
            "alerts_count": len(state_out.get("alerts_emitted") or []),
            "errors": state_out.get("errors"),
            "node_trace": state_out.get("node_trace"),
            "total_latency_s": round(total, 3),
            "final_response_preview": (state_out.get("final_response") or "")[:300],
        }
        with TRACES_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao gravar trace: %s", e)

    return state_out


# ────────────────────────────────────────────────────────────────────────
# Exportação de diagrama
# ────────────────────────────────────────────────────────────────────────

def export_diagram(out_dir: Path | str = "docs") -> dict[str, Path]:
    """Salva o diagrama em Mermaid (.md) e tenta gerar PNG.

    Retorna dict {formato: path} para cada artefato gerado com sucesso.
    PNG requer rede (mermaid.ink) — pode falhar silenciosamente.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    graph = _get_graph()
    result: dict[str, Path] = {}

    # 1) Mermaid automático (string)
    try:
        mermaid = graph.get_graph().draw_mermaid()
        path = out_dir / "langgraph_flow_auto.md"
        content = (
            "# Diagrama do grafo — gerado automaticamente\n\n"
            "Este arquivo é gerado por `assistant/graph.py:export_diagram()`.\n"
            "Para a versão escrita à mão (mais legível pro relatório), veja "
            "[`langgraph_flow.md`](langgraph_flow.md).\n\n"
            "```mermaid\n" + mermaid.strip() + "\n```\n"
        )
        path.write_text(content, encoding="utf-8")
        result["mermaid_auto"] = path
        print(f"✓ Mermaid (auto): {path}")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Mermaid auto falhou: {e}")

    # 2) PNG via mermaid.ink (pode falhar sem internet)
    try:
        png = graph.get_graph().draw_mermaid_png()
        path = out_dir / "langgraph_flow.png"
        path.write_bytes(png)
        result["png"] = path
        print(f"✓ PNG: {path}")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ PNG falhou (sem internet ou mermaid.ink indisponível?): {e}")

    return result


# ────────────────────────────────────────────────────────────────────────
# CLI: exporta diagrama + smoke test 1 query
# ────────────────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    """Roda 1 query simples pra confirmar que o grafo executa."""
    print()
    print("=" * 72)
    print("  Smoke test: 1 query no grafo completo")
    print("=" * 72)
    question = "Qual o protocolo para crise asmática?"
    print(f"  Pergunta: {question}")
    print()
    t0 = time.monotonic()
    state = run_medical_graph(question=question, patient_id=None)
    total = time.monotonic() - t0

    print(f"  ✓ executado em {total:.2f}s")
    print(f"  request_id:      {state.get('request_id')}")
    print(f"  intent:          {state.get('intent')}")
    print(f"  urgency:         {state.get('urgency')}")
    print(f"  rag_has_sources: {state.get('rag_has_sources')}")
    print(f"  patient_data:    {'sim' if state.get('patient_data') else 'não'}")
    print(f"  pending_exams:   {len(state.get('pending_exams') or [])}")
    print(f"  bypass_detected: {state.get('bypass_detected')}")
    triggered_input = [r for r in (state.get('input_guardrails_triggered') or []) if r.get('triggered')]
    triggered_output = [r for r in (state.get('output_guardrails_triggered') or []) if r.get('triggered')]
    print(f"  input guardrails triggered:  {[r['guardrail_name'] for r in triggered_input]}")
    print(f"  output guardrails triggered: {[r['guardrail_name'] for r in triggered_output]}")
    print(f"  alerts_emitted:  {len(state.get('alerts_emitted') or [])}")
    print(f"  errors:          {state.get('errors')}")
    print()
    print("  Trace:")
    for entry in state.get("node_trace", []):
        print(f"    - {entry['node']:<24s} {entry['latency_s']:>6.3f}s  {entry['summary']}")
    print()
    print("  Resposta (primeiros 400 chars):")
    print("  " + "-" * 68)
    resp = state.get("final_response") or "(vazio)"
    for line in resp[:400].split("\n"):
        print(f"  {line}")
    if len(resp) > 400:
        print("  […]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Grafo LangGraph (Fase 5)")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="exportar diagrama mas não rodar smoke test (rápido)")
    args = parser.parse_args()

    print("=" * 72)
    print("  Exportando diagrama do grafo")
    print("=" * 72)
    out = export_diagram("docs")
    print()
    print(f"  artefatos gerados: {list(out.keys())}")

    if args.skip_smoke:
        return 0
    return _smoke_test()


if __name__ == "__main__":
    sys.exit(main())
