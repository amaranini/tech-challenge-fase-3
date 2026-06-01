"""Módulo de guardrails unificado (Fase 6).

Cinco categorias:
- PRESCRICAO_DIRETA       (block, output)
- DIAGNOSTICO_DEFINITIVO  (block, output)
- DECISAO_CLINICA_FINAL   (block, output)
- BYPASS_ATTEMPT          (block, INPUT)
- FORA_ESCOPO_RESIDUAL    (warning, output)

Uso básico:
    from assistant.guardrails import (
        run_input_guardrails, run_output_guardrails,
        apply_guardrails_to_response,
    )

CLI de smoke test:
    uv run python -m assistant.guardrails "Prescreva 500mg de amoxicilina"
"""

from assistant.guardrails.base import Guardrail, GuardrailResult
from assistant.guardrails.bypass import BypassAttemptGuardrail
from assistant.guardrails.clinical_decision import ClinicalDecisionGuardrail
from assistant.guardrails.diagnosis import DiagnosisGuardrail
from assistant.guardrails.prescription import PrescriptionGuardrail
from assistant.guardrails.registry import (
    ALL_GUARDRAILS,
    INPUT_GUARDRAILS,
    OUTPUT_GUARDRAILS,
    apply_guardrails_to_response,
    list_guardrails,
    run_input_guardrails,
    run_output_guardrails,
)
from assistant.guardrails.scope import ScopeResidualGuardrail

__all__ = [
    "Guardrail",
    "GuardrailResult",
    "PrescriptionGuardrail",
    "DiagnosisGuardrail",
    "ClinicalDecisionGuardrail",
    "BypassAttemptGuardrail",
    "ScopeResidualGuardrail",
    "INPUT_GUARDRAILS",
    "OUTPUT_GUARDRAILS",
    "ALL_GUARDRAILS",
    "list_guardrails",
    "run_input_guardrails",
    "run_output_guardrails",
    "apply_guardrails_to_response",
]
