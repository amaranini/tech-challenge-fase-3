"""Estado compartilhado entre os nós do grafo LangGraph da Fase 5.

`MedicalState` é o TypedDict que cada nó recebe e ao qual cada nó devolve um
dict parcial (só as chaves que mudou). LangGraph faz merge automático.

Campos acumulativos usam `Annotated[list, operator.add]`. Por que: o default
do LangGraph é SUBSTITUIR uma chave quando um nó a retorna. Para
`node_trace`, `errors`, `alerts_emitted` e `guardrail_flags` a gente quer
CONCATENAR (cada nó adiciona à lista existente). O reducer `operator.add`
diz isso ao LangGraph.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional

# Pydantic v2 (chamado internamente pelo LangGraph p/ schema do estado)
# requer typing_extensions.TypedDict em Python < 3.12.
from typing_extensions import TypedDict


class NodeTraceEntry(TypedDict):
    """Uma entrada no trace, registrada por cada nó ao terminar."""

    node: str
    timestamp: str       # ISO 8601
    latency_s: float
    summary: str         # uma frase curta com a decisão/saída do nó
    error: Optional[str]  # None se ok; mensagem curta se houve exceção engolida


class AlertEntry(TypedDict):
    """Um alerta emitido pelo nó 8 (urgência alta)."""

    timestamp: str
    patient_id: Optional[str]
    question: str
    urgency: str
    summary: str


class MedicalState(TypedDict, total=False):
    """Estado completo do grafo. `total=False` permite estado parcial nos retornos dos nós."""

    # ─── Entrada ─────────────────────────────────────────────────────────
    question: str
    patient_id: Optional[str]

    # ─── Classificação (Nós 1 e 2) ──────────────────────────────────────
    intent: Optional[Literal["clinica", "administrativa", "fora_de_escopo"]]
    urgency: Optional[Literal["alta", "media", "baixa"]]

    # ─── Dados consultados (Nós 3, 4, 5) ────────────────────────────────
    patient_data: Optional[dict]
    pending_exams: Optional[list[dict]]
    rag_chunks: Optional[list[dict]]
    rag_has_sources: bool

    # ─── Geração e checagem (Nós 6, 7) ──────────────────────────────────
    draft_response: Optional[str]
    guardrail_flags: Annotated[list[str], operator.add]
    was_rewritten: bool

    # ─── Saída (Nós 8, 9) ───────────────────────────────────────────────
    final_response: Optional[str]
    alerts_emitted: Annotated[list[AlertEntry], operator.add]

    # ─── Observabilidade (todos os nós) ─────────────────────────────────
    node_trace: Annotated[list[NodeTraceEntry], operator.add]
    errors: Annotated[list[str], operator.add]


def initial_state(question: str, patient_id: Optional[str] = None) -> MedicalState:
    """Constrói o State inicial pra uma nova execução do grafo.

    Todos os campos acumulativos são inicializados como listas vazias —
    o reducer `operator.add` exige que a chave exista pra somar nela.
    """
    return MedicalState(
        question=question,
        patient_id=patient_id,
        intent=None,
        urgency=None,
        patient_data=None,
        pending_exams=None,
        rag_chunks=None,
        rag_has_sources=False,
        draft_response=None,
        guardrail_flags=[],
        was_rewritten=False,
        final_response=None,
        alerts_emitted=[],
        node_trace=[],
        errors=[],
    )
