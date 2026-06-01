"""GUARDRAIL_DECISAO_CLINICA_FINAL — bloqueia decisões médicas finais no output.

Razão clínica: alta hospitalar, internação, indicação cirúrgica, suspensão
de medicação contínua são decisões com consequências clínicas e legais
diretas. O assistente sugere CONSIDERAR ou DISCUTIR, mas a decisão é do
médico responsável.

Padrões cobertos:
- Alta: "pode receber alta", "está apto/liberado para alta"
- Internação: "deve ser internado", "indicar internação/UTI"
- Cirurgia: "indicar cirurgia", "encaminhar para cirurgia"
- Suspensão de medicação: "suspender [droga]" (sem qualificador "considerar")
- Negativas categóricas: "não precisa internar", "não precisa de UTI"

Ação: rewrite via LLM, transformando em "considerar [decisão] se [critérios]"
ou "discutir [decisão] com [especialista]".
"""

from __future__ import annotations

import re

from assistant.guardrails.base import Guardrail, GuardrailResult

# Conjuntos de drogas comuns pra detectar "suspender [droga]".
# Lista deliberadamente curta — falsos negativos (drogas raras não detectadas)
# são melhores que falsos positivos.
_DRUGS_COMMON = (
    "metformina", "insulina", "warfarina", "aspirina", "AAS",
    "amoxicilina", "ciprofloxacino", "azitromicina",
    "losartana", "enalapril", "captopril", "atenolol",
    "omeprazol", "ranitidina", "dipirona", "paracetamol",
    "prednisona", "corticoide", "corticoterapia",
)

_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("pode_dar_alta",
     re.compile(r"\bpode(\s+\w+){0,2}\s+alta\b", re.IGNORECASE)),
    ("apto_para_alta",
     re.compile(r"\b(está|é)\s+(apto|liberado)\s+(para|pra|p/)\s+alta\b",
                re.IGNORECASE)),
    ("deve_ser_internado",
     re.compile(r"\bdeve\s+ser\s+internado\b", re.IGNORECASE)),
    ("indicar_internacao",
     re.compile(r"\bindicar\s+(internação|UTI|hospitalização)\b", re.IGNORECASE)),
    ("encaminhar_internacao",
     re.compile(r"\bencaminhar\s+para\s+(internação|UTI|hospitalização)\b",
                re.IGNORECASE)),
    ("indicar_cirurgia",
     re.compile(r"\bindicar\s+(cirurgia|procedimento\s+cirúrgico)\b", re.IGNORECASE)),
    ("encaminhar_cirurgia",
     re.compile(r"\bencaminhar\s+(para|pra|p/)\s+cirurgia\b", re.IGNORECASE)),
    ("suspender_droga",
     re.compile(
         r"\b(suspender|interromper|descontinuar)\s+(a\s+|o\s+)?(" +
         "|".join(_DRUGS_COMMON) + r")\b",
         re.IGNORECASE,
     )),
    ("suspender_imediato",
     re.compile(
         r"\b(suspender|interromper|descontinuar)\s+\w+\s+(imediatamente|agora|hoje)\b",
         re.IGNORECASE,
     )),
    ("nao_precisa_internar",
     re.compile(
         r"\bnão\s+precisa\s+(internar|ser\s+internado|de\s+UTI|de\s+cirurgia|de\s+hospitalização)\b",
         re.IGNORECASE,
     )),
)


class ClinicalDecisionGuardrail(Guardrail):
    """Bloqueia tomada direta de decisões clínicas finais."""

    name = "decisao_clinica_final"
    level = "block"
    applies_to = "output"

    def detect(self, text: str) -> GuardrailResult:
        matched: list[str] = []
        for label, pattern in _PATTERNS:
            m = pattern.search(text)
            if m:
                matched.append(f"{label}:{m.group(0)}")

        triggered = bool(matched)
        return self._make_result(
            triggered=triggered,
            matched=matched,
            severity=0.8 if triggered else 0.0,
            message=(
                f"Decisão clínica final detectada: {matched[0]}"
                if triggered else ""
            ),
        )

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        return (
            "Você é um revisor clínico. A resposta abaixo contém decisão clínica "
            "que cabe ao médico assistente (alta, internação, cirurgia, suspensão "
            "de medicação). Reescreva transformando essas afirmações em sugestões "
            "para o médico avaliar.\n\n"
            "REGRAS:\n"
            "- 'pode receber alta' → 'avaliar critérios de alta; considerar liberação se [critérios]'\n"
            "- 'deve ser internado' → 'considerar internação se [critérios clínicos]'\n"
            "- 'indicar cirurgia' → 'discutir indicação cirúrgica com [especialista]'\n"
            "- 'suspender X' → 'reavaliar X à luz de [contexto]; o médico assistente pode considerar suspensão'\n"
            "- Preserve raciocínio clínico, sinais de alerta, critérios.\n"
            "- Use português brasileiro formal.\n"
            "- Encerre com: 'Esta orientação é apoio à decisão; a conduta final "
            "  cabe ao médico assistente.'\n\n"
            f"Padrões detectados: {', '.join(result.matched_patterns)}\n\n"
            "=== TEXTO ORIGINAL ===\n"
            f"{original_text}\n\n"
            "=== TEXTO REESCRITO ===\n"
        )
