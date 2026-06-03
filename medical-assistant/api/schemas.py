"""Schemas Pydantic da API (Fase 7).

Validação automática + docs interativas em /docs (FastAPI). Tipos claros
por campo. Mantemos os modelos enxutos pra demo — a explainability vem
como `dict` opaco no payload (já há um schema pesado dela do lado do core).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ────────────────────────────────────────────────────────────────────────
# Consulta
# ────────────────────────────────────────────────────────────────────────

class ConsultRequest(BaseModel):
    """Body do POST /consult.

    `patient_id` é opcional — perguntas gerais sobre protocolo não precisam
    de paciente. Quando vier, deve casar com o padrão P\\d{4} (4 dígitos).
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Pergunta clínica do médico (PT-BR).",
    )
    patient_id: Optional[str] = Field(
        None,
        pattern=r"^P\d{4}$",
        description="ID do paciente (formato P0001). Opcional.",
    )


class ConsultResponse(BaseModel):
    """Resposta do POST /consult.

    `explanation` é a ficha de raciocínio (output de
    `assistant.explainability.build_explanation`). Schema dela documentado
    no módulo de explainability — aqui mantemos como dict pra evitar
    duplicação.
    """

    request_id: str = Field(..., description="UUID único da execução.")
    final_response: str = Field(..., description="Resposta final ao médico.")
    explanation: dict[str, Any] = Field(
        ...,
        description="Ficha de raciocínio (classification, sources, guardrails, etc).",
    )
    latency_ms: int = Field(..., ge=0, description="Latência total da execução.")
    urgency: Optional[Literal["alta", "media", "baixa"]] = None
    intent: Optional[Literal["clinica", "administrativa", "fora_de_escopo"]] = None
    was_rewritten: bool = Field(
        ...,
        description="True se algum guardrail block disparou e a resposta foi reescrita.",
    )
    has_alert: bool = Field(
        ...,
        description="True se um alerta de urgência alta foi emitido.",
    )


# ────────────────────────────────────────────────────────────────────────
# Pacientes
# ────────────────────────────────────────────────────────────────────────

class PatientSummary(BaseModel):
    """Item da lista de pacientes — id + dados não-sensíveis."""

    id: str
    nome: str
    idade: int
    sexo: str


class PendingExam(BaseModel):
    tipo_exame: str
    data_solicitacao: str
    prioridade: str


class PatientDetail(PatientSummary):
    """Prontuário completo + exames pendentes da nova tabela (Fase 5)."""

    alergias: str = ""
    medicacoes_atuais: str = ""
    historico_resumido: str = ""
    pending_exams: list[PendingExam] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────
# Auditoria
# ────────────────────────────────────────────────────────────────────────

class AuditListItem(BaseModel):
    """Linha resumida pra listagem de auditoria.

    Flags `has_guardrail` e `has_alert` são computadas no servidor a partir
    do JOIN com guardrail_events/alerts — economiza requisições da UI.
    """

    request_id: str
    ts: str
    question: str
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    intent: Optional[str] = None
    urgency: Optional[str] = None
    bypass_detected: bool = False
    has_guardrail: bool = False
    has_alert: bool = False
    latency_ms: Optional[int] = None


class GuardrailEvent(BaseModel):
    guardrail_name: str
    level: str
    applies_to: str
    triggered: bool
    matched_patterns: list[str] = Field(default_factory=list)
    severity: float = 0.0
    message: str = ""
    action_taken: Optional[str] = None


class AlertEvent(BaseModel):
    request_id: str
    ts: str
    patient_id: Optional[str]
    urgency: str
    summary: str
    acknowledged: bool = False


class RagRetrieval(BaseModel):
    query: str
    top_k_results: list[dict[str, Any]] = Field(default_factory=list)
    had_sources: bool = False


class AuditDetail(BaseModel):
    """Detalhe completo de uma interação — pra modal de auditoria."""

    model_config = ConfigDict(extra="allow")

    request_id: str
    ts: str
    question: str
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    intent: Optional[str] = None
    urgency: Optional[str] = None
    bypass_detected: bool = False
    response: Optional[str] = None
    latency_ms: Optional[int] = None
    rag_has_sources: bool = False
    state_snapshot: Optional[dict[str, Any]] = None
    guardrail_events: list[GuardrailEvent] = Field(default_factory=list)
    alerts: list[AlertEvent] = Field(default_factory=list)
    rag_retrievals: list[RagRetrieval] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────
# Health
# ────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Diagnóstico do servidor — pro UI desenhar status no topo."""

    status: Literal["ok", "degraded"]
    model_loaded: bool
    db_accessible: bool
    audit_db_accessible: bool
    version: str
    startup_seconds: Optional[float] = None
