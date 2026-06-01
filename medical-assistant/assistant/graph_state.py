"""Estado compartilhado entre os nós do grafo LangGraph.

`MedicalState` é o TypedDict que cada nó recebe e ao qual cada nó devolve um
dict parcial (só as chaves que mudou). LangGraph faz merge automático.

Campos acumulativos usam `Annotated[list, operator.add]`. Por que: o default
do LangGraph é SUBSTITUIR uma chave quando um nó a retorna. Para
`node_trace`, `errors`, `alerts_emitted`, `input_guardrails_triggered` e
`output_guardrails_triggered` a gente quer CONCATENAR (cada nó adiciona à
lista existente). O reducer `operator.add` diz isso ao LangGraph.

Atualizações Fase 6:
- Adicionados: `request_id`, `input_guardrails_triggered`,
  `output_guardrails_triggered`, `bypass_detected`.
- Removidos: `guardrail_flags` e `was_rewritten` da Fase 5 (substituídos
  pelos novos campos que carregam mais informação por GuardrailResult).
"""

from __future__ import annotations

import operator
import uuid
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

    # ─── Identidade da interação (Fase 6) ───────────────────────────────
    request_id: str   # UUID único — chave estrangeira para audit DB

    # ─── Entrada ─────────────────────────────────────────────────────────
    question: str
    patient_id: Optional[str]

    # ─── Guardrails de entrada (Fase 6, Nó 0) ───────────────────────────
    # Sem reducer: input_guardrail_check escreve uma única vez (replace).
    input_guardrails_triggered: list[dict]
    bypass_detected: bool

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
    # Sem reducer: guardrail_check escreve (replace) e rewrite_node atualiza
    # in-place + replace; reducer add duplicaria a lista.
    output_guardrails_triggered: list[dict]

    # ─── Saída (Nós 8, 9) ───────────────────────────────────────────────
    final_response: Optional[str]
    alerts_emitted: Annotated[list[AlertEntry], operator.add]

    # ─── Explainability (Bloco 3 — Fase 6) ──────────────────────────────
    explanation: Optional[dict]

    # ─── Observabilidade (todos os nós) ─────────────────────────────────
    node_trace: Annotated[list[NodeTraceEntry], operator.add]
    errors: Annotated[list[str], operator.add]


def initial_state(
    question: str,
    patient_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> MedicalState:
    """Constrói o State inicial pra uma nova execução do grafo.

    Todos os campos acumulativos são inicializados como listas vazias —
    o reducer `operator.add` exige que a chave exista pra somar nela.

    Args:
        question: pergunta do usuário.
        patient_id: opcional — se não vier, Nó 3 tenta extrair via regex.
        request_id: opcional — se não vier, gera UUID novo. Permitir
            override é útil em testes pra controle do ID.
    """
    return MedicalState(
        request_id=request_id or str(uuid.uuid4()),
        question=question,
        patient_id=patient_id,
        input_guardrails_triggered=[],
        bypass_detected=False,
        intent=None,
        urgency=None,
        patient_data=None,
        pending_exams=None,
        rag_chunks=None,
        rag_has_sources=False,
        draft_response=None,
        output_guardrails_triggered=[],
        final_response=None,
        alerts_emitted=[],
        explanation=None,
        node_trace=[],
        errors=[],
    )
