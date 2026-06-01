"""GUARDRAIL_BYPASS_ATTEMPT — detecta tentativas de burlar limites do assistente.

Razão de segurança: usuários (mesmo profissionais) podem tentar contornar
limitações pra obter respostas fora do escopo (prescrição direta, decisão
final, etc). Esses padrões merecem tratamento ESPECIAL — diferente de
'fora_de_escopo' simples:
- Recusa fixa, mais firme, citando a tentativa explicitamente.
- Audit dedicado com severity=1.0 (security event).
- NÃO passa pelo classify_intent do grafo (vai direto pro refuse).

Padrões cobertos (jailbreaks documentados):
- "ignore (suas/as) regras/instruções"
- "esqueça (o que / as instruções)"
- "responda sem (filtro / restrições)"
- "você (agora é / é agora) [persona]"
- "pretenda / finja ser"
- "modo (desenvolvedor / developer / sem filtro / admin / root)"
- "DAN mode" (jailbreak histórico ChatGPT)
- "you are now / ignore all previous instructions" (em inglês — comum em copy-paste)
- "sistema:" (tentativa de role-play como mensagem de sistema)

NOTA DE DESIGN: este é o ÚNICO guardrail input-side. Aplicado no Nó 0 do
grafo (novo, antes do classify_intent). Os demais 4 são output-side.
"""

from __future__ import annotations

import re

from assistant.guardrails.base import Guardrail, GuardrailResult

_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("ignore_rules",
     re.compile(r"\bignor[ea]\s+(suas?\s+|as\s+|todas\s+as\s+)?(regras|instruções|prompt|sistema)\b",
                re.IGNORECASE)),
    ("forget_instructions",
     re.compile(r"\besque[çc]a\s+(o\s+que|tudo|as?\s+(regras|instruções)|as\s+regras)\b",
                re.IGNORECASE)),
    ("respond_without_filter",
     re.compile(r"\bresponda\s+sem\s+(filtro|restri[çc]ões|limit)\b", re.IGNORECASE)),
    ("you_are_now",
     re.compile(r"\bvocê\s+(agora|é\s+agora|agora\s+é)\s+(é\s+)?(um|uma)\s+\w+\s+sem\s+(restri[çc]ões|filtro|limit)\b",
                re.IGNORECASE)),
    ("pretend_to_be",
     re.compile(r"\b(prete[nd]da?|finj[ae]|aja?\s+como)\s+ser\b", re.IGNORECASE)),
    ("developer_mode",
     re.compile(r"\bmodo\s+(desenvolvedor|developer|sem.?filtro|root|admin|deus|god)\b",
                re.IGNORECASE)),
    ("dan_mode",
     re.compile(r"\b(dan\s+mode|do\s+anything\s+now)\b", re.IGNORECASE)),
    ("ignore_previous_en",
     re.compile(r"\b(you\s+are\s+now|ignore\s+all\s+(previous|prior)\s+instructions)\b",
                re.IGNORECASE)),
    ("system_role_inject",
     re.compile(r"^\s*(sistema|system)\s*:\s", re.IGNORECASE | re.MULTILINE)),
)

REFUSE_MESSAGE = (
    "Detectei uma tentativa de modificar minhas instruções de funcionamento. "
    "Esta interface é restrita a perguntas clínicas dentro dos limites de apoio "
    "à decisão definidos pela instituição. Reformule sua pergunta dentro do "
    "escopo clínico e ficarei feliz em ajudar."
)


class BypassAttemptGuardrail(Guardrail):
    """Detecta jailbreaks no INPUT do usuário."""

    name = "bypass_attempt"
    level = "block"
    applies_to = "input"

    def detect(self, text: str) -> GuardrailResult:
        matched: list[str] = []
        for label, pattern in _PATTERNS:
            m = pattern.search(text)
            if m:
                matched.append(f"{label}:{m.group(0).strip()}")

        triggered = bool(matched)
        return self._make_result(
            triggered=triggered,
            matched=matched,
            severity=1.0 if triggered else 0.0,  # security event — máxima severidade
            message=(
                f"Tentativa de bypass detectada: {matched[0]}"
                if triggered else ""
            ),
        )

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        # Não usado — bypass é input-side, ação é recusa fixa via REFUSE_MESSAGE.
        return REFUSE_MESSAGE
