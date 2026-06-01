"""GUARDRAIL_DIAGNOSTICO_DEFINITIVO — bloqueia afirmações categóricas de diagnóstico.

Razão clínica: diagnóstico definitivo é decisão médica baseada em quadro
clínico + exames complementares. O assistente deve usar tom probabilístico
("provavelmente", "hipóteses incluem", "considerar") e sugerir os exames
confirmatórios. Tom categórico é problemático mesmo quando o quadro é típico.

Padrões detectados (apenas MARCADORES INEQUÍVOCOS de certeza, pra evitar
falsos positivos quando o modelo está repetindo info do prontuário):
- "diagnóstico (definitivo|fechado|certo|conclusivo) de"
- "trata-se de"
- "com certeza (é|tem|trata-se)"
- "é/trata-se de um caso (clássico|definitivo) de"
- "definitivamente (é|tem|trata-se)"
- "sem dúvida (é|tem)"

NOTA DE DESIGN: não incluímos "o paciente TEM [doença]" sozinho porque tem
alto risco de falso positivo — pode ser leitura legítima de prontuário
("o paciente tem diabetes registrado no histórico"). Foco em marcadores
de certeza explícita.

Ação: rewrite via LLM, transformando em tom probabilístico + sugestão de
exames confirmatórios.
"""

from __future__ import annotations

import re

from assistant.guardrails.base import Guardrail, GuardrailResult

# Cada padrão = uma forma de afirmar diagnóstico com certeza.
_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("diagnostico_definitivo",
     re.compile(r"\bdiagn[óo]stico\s+(definitivo|fechado|certo|conclusivo)\s+(é|de)\b",
                re.IGNORECASE)),
    ("trata_se_de",
     re.compile(r"\btrata-se\s+de\b", re.IGNORECASE)),
    ("com_certeza",
     re.compile(r"\bcom\s+certeza\s+(é|tem|trata-se)\b", re.IGNORECASE)),
    ("caso_classico",
     re.compile(r"\b(é|trata-se\s+de)\s+um\s+caso\s+(clássico|definitivo|claro)\s+de\b",
                re.IGNORECASE)),
    ("definitivamente",
     re.compile(r"\bdefinitivamente\s+(é|tem|trata-se)\b", re.IGNORECASE)),
    ("sem_duvida",
     re.compile(r"\bsem\s+dúvida\s+(é|tem|trata-se)\b", re.IGNORECASE)),
)


class DiagnosisGuardrail(Guardrail):
    """Bloqueia afirmações categóricas de diagnóstico no output."""

    name = "diagnostico_definitivo"
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
            severity=0.7 if triggered else 0.0,
            message=(
                f"Diagnóstico categórico detectado: {matched[0]}"
                if triggered else ""
            ),
        )

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        return (
            "Você é um revisor clínico. Reescreva a resposta abaixo trocando "
            "afirmações categóricas de diagnóstico por linguagem probabilística "
            "com sugestão dos exames confirmatórios apropriados.\n\n"
            "REGRAS:\n"
            "- Troque 'trata-se de X' por 'os achados são compatíveis com X; considere [exame]'.\n"
            "- Troque 'diagnóstico definitivo de X' por 'hipótese principal: X; confirmar com [exame]'.\n"
            "- Troque 'com certeza é X' por 'X é a hipótese mais provável, mas considere também [diff]'.\n"
            "- Preserve as informações técnicas (sintomas, achados, conduta proposta).\n"
            "- Use português brasileiro formal.\n"
            "- Encerre com: 'Esta orientação é apoio à decisão; a conduta final "
            "  cabe ao médico assistente.'\n\n"
            f"Padrões detectados: {', '.join(result.matched_patterns)}\n\n"
            "=== TEXTO ORIGINAL ===\n"
            f"{original_text}\n\n"
            "=== TEXTO REESCRITO ===\n"
        )
