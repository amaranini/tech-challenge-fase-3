"""GUARDRAIL_FORA_ESCOPO_RESIDUAL — detecta deriva de tema no OUTPUT (warning).

Razão clínica: o Nó 1 (classify_intent) já barrou perguntas óbvias fora de
escopo. Este guardrail é a 2ª linha — detecta quando o modelo SAIU do escopo
dentro do output mesmo a pergunta tendo sido clínica.

Cenários típicos: pergunta sobre dieta (clinica) → resposta vira receita
culinária; pergunta sobre prevenção de eventos cardiovasculares (clinica)
→ resposta cita filme com tema médico.

Por que `warning` (não block): conteúdos não-clínicos podem aparecer
legitimamente como contexto periférico ("paciente teve mal súbito durante
jogo de futebol"). Bloquear seria excessivo. Solução: anexa NOTA ao final
da resposta lembrando o escopo, sem reescrever.

Padrões cobertos no OUTPUT:
- Culinária: "receita de/para [não-clínico]", "ingredientes:\n"
- Código: "import X", "def func(", "```python"
- Música: "letra da/de música"
- Esporte: "campeonato/time de futebol/basquete/..."
- Entretenimento: "filme/série/novela do/da/de"
"""

from __future__ import annotations

import re

from assistant.guardrails.base import Guardrail, GuardrailResult

_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    # Culinária — receita seguida de preposição + termo não-médico
    ("receita_culinaria",
     re.compile(
         r"\breceita\s+(de|para)\s+"
         r"(?!medicamento|conduta|emergência|antibiótico|insulinização|hidratação|"
         r"emergência\s+hipertensiva|hidratação\s+venosa|infusão)"
         r"(bolo|pão|sopa|pizza|biscoito|massa|torta|frango|carne|sobremesa|salada|"
         r"caldo|risoto|drink|cuca|brigadeiro|panqueca|omelete|coxinha)\b",
         re.IGNORECASE,
     )),
    ("ingredientes_lista",
     re.compile(r"\bingredientes:\s*\n", re.IGNORECASE)),
    # Código — só keywords Python claras com palavra adjacente
    ("import_python",
     re.compile(r"\bimport\s+[a-z_][\w]+\b")),
    ("def_python",
     re.compile(r"\bdef\s+[a-z_][\w]*\s*\(")),
    ("code_fence_python",
     re.compile(r"```\s*python\b", re.IGNORECASE)),
    # Música
    ("letra_musica",
     re.compile(r"\bletra\s+(da|de|de\s+uma)\s+música\b", re.IGNORECASE)),
    # Esporte — duas variantes:
    # (a) campeonato/time DE/DO/DA + esporte específico
    # (b) campeonato + adjetivo nacional/regional (brasileiro, mundial, paulista, etc)
    ("esporte_competicao",
     re.compile(
         r"\b(campeonato|time)\s+(de|do|da)\s+(futebol|basquete|vôlei|tênis|natação)\b",
         re.IGNORECASE,
     )),
    ("esporte_competicao_adj",
     re.compile(
         r"\bcampeonato\s+(brasileiro|mundial|paulista|carioca|gaúcho|estadual|nacional|europeu|americano)\b",
         re.IGNORECASE,
     )),
    # Entretenimento
    ("filme_serie_novela",
     re.compile(r"\b(filme|série|novela|seriado)\s+(do|da|de|sobre)\s+\w+\b",
                re.IGNORECASE)),
)

# Nota anexada ao final da resposta quando o guardrail dispara.
SCOPE_NOTE = (
    "\n\n*Nota: parte desta resposta parece ter ido além do escopo clínico. "
    "Lembre-se: esta interface é restrita a apoio à decisão clínica.*"
)


class ScopeResidualGuardrail(Guardrail):
    """Detecta deriva de escopo no OUTPUT (warning, não bloqueia)."""

    name = "fora_escopo_residual"
    level = "warning"
    applies_to = "output"

    def detect(self, text: str) -> GuardrailResult:
        matched: list[str] = []
        for label, pattern in _PATTERNS:
            m = pattern.search(text)
            if m:
                matched.append(f"{label}:{m.group(0)[:60]}")

        triggered = bool(matched)
        return self._make_result(
            triggered=triggered,
            matched=matched,
            severity=0.4 if triggered else 0.0,  # baixa — só warning
            message=(
                f"Resposta tocou tema não-clínico: {matched[0]}"
                if triggered else ""
            ),
        )

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        # Não usado: nível warning não reescreve. Mantemos por consistência da ABC.
        return original_text + SCOPE_NOTE
