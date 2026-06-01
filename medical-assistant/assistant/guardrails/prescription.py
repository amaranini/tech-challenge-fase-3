"""GUARDRAIL_PRESCRICAO_DIRETA — bloqueia prescrições com dose explícita.

Razão clínica: o assistente é ferramenta de APOIO à decisão. Prescrição
medicamentosa carrega responsabilidade legal e clínica do médico assistente.
O modelo pode citar dose de REFERÊNCIA, mas não pode "prescrever".

Padrões cobertos (qualquer um dispara):
1. Verbo imperativo + droga + dose numérica:
   "Prescreva amoxicilina 500mg" / "Recomendo 1g de paracetamol"
2. Droga + dose + posologia explícita:
   "Amoxicilina 500mg a cada 8 horas" / "1g de 6/6h"
3. Dose por extenso:
   "Quinhentos miligramas de amoxicilina" / "Um grama via oral"

Ação: rewrite via LLM, removendo a prescrição imperativa e mantendo a
informação técnica como referência ("a dose de referência é X, prescrição
é decisão do médico assistente").

Evolui o detector da Fase 5 (Nó 7, `_PRESCRIPTION_VERB_PATTERN` +
`_PRESCRIPTION_POSOLOGY_PATTERN`), adicionando o padrão de números por
extenso (pt-BR).
"""

from __future__ import annotations

import re

from assistant.guardrails.base import Guardrail, GuardrailResult

# Padrão 1: verbo imperativo + dose numérica em até 4 palavras de distância.
# Cobre "prescrevo amoxicilina 500mg" E "prescreva 500mg de amoxicilina".
_PATTERN_VERB_DOSE = re.compile(
    r"\b(prescrev[oa]|prescreva|recomendo|administre|administrar|tome|use)\b"
    r"(?:\s+[\w\-]+){0,4}"
    r"\s+\d+[\.,]?\d*\s*(mg|ml|g|UI|mcg|mcg/kg)\b",
    re.IGNORECASE,
)

# Padrão 2: droga + dose + posologia ("amoxicilina 500mg a cada 8h").
_PATTERN_DRUG_DOSE_POSOLOGY = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÇ]?[a-záéíóúâêôç\-]{4,}\s+\d+[\.,]?\d*\s*(mg|ml|g|UI|mcg)"
    r"\s+(a\s+cada|\d+\s*x\s*ao\s*dia|\d+\s*vezes\s*ao\s*dia|de\s+\d+\s*/\s*\d+\s*h)\b",
    re.IGNORECASE,
)

# Padrão 3 (NOVO): dose por extenso seguida de unidade por extenso.
# Cobre "quinhentos miligramas", "um grama", "dois mililitros", etc.
_NUMEROS_EXTENSO = (
    r"(?:um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|"
    r"vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|"
    r"cem|cento|duzentos|trezentos|quatrocentos|quinhentos|seiscentos|"
    r"setecentos|oitocentos|novecentos|mil)"
)
_PATTERN_DOSE_EXTENSO = re.compile(
    rf"\b{_NUMEROS_EXTENSO}(?:\s+e\s+{_NUMEROS_EXTENSO})?\s+"
    r"(miligramas?|gramas?|mililitros?|microgramas?|miligrama|grama)\b",
    re.IGNORECASE,
)

# Padrão 4: híbrido — número numérico + unidade por extenso ("1 grama", "500 miligramas").
# Comum em respostas LLM em pt-BR.
_PATTERN_DOSE_HYBRID = re.compile(
    r"\b\d+[\.,]?\d*\s+"
    r"(miligramas?|gramas?|mililitros?|microgramas?|miligrama|grama)\b",
    re.IGNORECASE,
)


class PrescriptionGuardrail(Guardrail):
    """Bloqueia prescrição medicamentosa direta com dose."""

    name = "prescricao_direta"
    level = "block"
    applies_to = "output"

    def detect(self, text: str) -> GuardrailResult:
        matched: list[str] = []
        m1 = _PATTERN_VERB_DOSE.search(text)
        m2 = _PATTERN_DRUG_DOSE_POSOLOGY.search(text)
        m3 = _PATTERN_DOSE_EXTENSO.search(text)
        m4 = _PATTERN_DOSE_HYBRID.search(text)

        if m1:
            matched.append(f"verb_dose:{m1.group(0)}")
        if m2:
            matched.append(f"drug_dose_posology:{m2.group(0)}")
        if m3:
            matched.append(f"dose_extenso:{m3.group(0)}")
        if m4 and not m1 and not m2 and not m3:
            # Hybrid só conta se nenhum dos outros já casou (evita flag duplicado)
            matched.append(f"dose_hybrid:{m4.group(0)}")

        triggered = bool(matched)
        return self._make_result(
            triggered=triggered,
            matched=matched,
            severity=0.9 if triggered else 0.0,
            message=(
                f"Prescrição direta detectada: {matched[0]}"
                if triggered else ""
            ),
        )

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        return (
            "Você é um revisor clínico. Reescreva a resposta abaixo removendo "
            "QUALQUER prescrição direta com dose. Em vez de 'prescrevo X mg' ou "
            "'Y mg de droga a cada Zh', use o formato:\n"
            "  'a dose de referência é X mg; a prescrição é decisão do médico assistente'.\n\n"
            "REGRAS:\n"
            "- Preserve toda informação técnica útil (mecanismo, indicação, "
            "  contraindicações, interações, monitorização).\n"
            "- Use português brasileiro formal.\n"
            "- Mantenha tamanho próximo ao original.\n"
            "- Encerre com: 'Esta orientação é apoio à decisão; a conduta final "
            "  cabe ao médico assistente.'\n\n"
            f"Padrões detectados: {', '.join(result.matched_patterns)}\n\n"
            "=== TEXTO ORIGINAL ===\n"
            f"{original_text}\n\n"
            "=== TEXTO REESCRITO ===\n"
        )
