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
# Lista deliberadamente curta de DOENÇAS GRAVES onde "o paciente tem X" é
# quase sempre afirmação diagnóstica do modelo (não citação de histórico).
# Risco baixo de FP — essas palavras raramente aparecem em prontuário sem
# qualificação. Mantemos lista MÍNIMA pra evitar over-detection.
_DOENCAS_GRAVES = (
    "câncer", "cancer", "tumor", "neoplasia", "metástase", "metastase",
    "leucemia", "linfoma", "melanoma",
    "aids", "hiv",
    "sepse", "choque séptico", "choque septico",
    "iam", "infarto agudo", "avc", "tep", "embolia pulmonar",
    "cirrose", "insuficiência renal", "insuficiencia renal",
    "insuficiência hepática", "insuficiencia hepatica",
    "insuficiência cardíaca", "insuficiencia cardiaca",
    "meningite", "endocardite",
)

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
    # NOVO: "paciente tem [doença grave]" — afirmação categórica direta.
    # Aceita até 2 palavras intermediárias (artigos, advérbios) entre verbo
    # e doença. Ex: "tem definitivamente câncer", "tem uma sepse grave".
    ("paciente_tem_doenca_grave",
     re.compile(
         r"\b(paciente\s+)?(tem|apresenta)\s+(\w+\s+){0,2}(?:" +
         "|".join(re.escape(d) for d in _DOENCAS_GRAVES) +
         r")\b",
         re.IGNORECASE,
     )),
    # NOVO: "diagnóstico [adjetivo]* confirmado de [doença]"
    # Pega "diagnóstico confirmado de X", "diagnóstico histopatológico
    # confirmado de X", etc — afirmação de exame confirmatório que o
    # modelo pode estar inventando.
    ("diagnostico_confirmado",
     re.compile(
         r"\bdiagn[óo]stico\s+(\w+\s+){0,2}confirmado\s+de\b",
         re.IGNORECASE,
     )),
    # NOVO: "paciente com [doença grave]" — descrição categórica do paciente,
    # comum em alucinações onde o modelo aceita a premissa do usuário.
    # Exclui qualificadores ("suspeita de", "hipótese de", "histórico de").
    ("paciente_com_doenca_grave",
     re.compile(
         r"\b(paciente|caso)\s+com\s+"
         r"(?!suspeita\s+|hipótese\s+|histórico\s+|antecedente\s+|risco\s+|possível\s+)"
         r"(diagnóstico\s+\w*\s*confirmado\s+de\s+|diagnóstico\s+de\s+)?"
         r"(?:" + "|".join(re.escape(d) for d in _DOENCAS_GRAVES) + r")\b",
         re.IGNORECASE,
     )),
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
