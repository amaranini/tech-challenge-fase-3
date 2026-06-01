"""Registry central — coordena os 5 guardrails da Fase 6.

Funções públicas:
- `run_input_guardrails(question)`: aplica TODOS os input-side guardrails.
- `run_output_guardrails(draft)`: aplica TODOS os output-side guardrails.
- `apply_guardrails_to_response(draft, llm)`: orquestra detect + ação
  (rewrite via LLM para blocks; nota anexada para warnings). Devolve
  o texto final + lista completa de results (todos os 4 output guardrails,
  triggered ou não — pra audit completo).

Decisão arquitetural: múltiplos blocks no mesmo output são tratados em
UMA chamada de LLM com instrução combinada — não em loop. Mais barato
e suficiente pra Fase 6. Aceita-se que ocasionalmente o LLM corrija um
mas esqueça outro; o próximo guardrail_check teria pegado isso, mas a
gente roda só 1 vez. Se vira problema empírico, evolui pra loop com
max_iterations=3.
"""

from __future__ import annotations

import logging
from typing import Iterable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from assistant.guardrails.base import Guardrail, GuardrailResult
from assistant.guardrails.bypass import REFUSE_MESSAGE, BypassAttemptGuardrail
from assistant.guardrails.clinical_decision import ClinicalDecisionGuardrail
from assistant.guardrails.diagnosis import DiagnosisGuardrail
from assistant.guardrails.prescription import PrescriptionGuardrail
from assistant.guardrails.scope import SCOPE_NOTE, ScopeResidualGuardrail

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────
# Catálogo
# ────────────────────────────────────────────────────────────────────────

INPUT_GUARDRAILS: tuple[Guardrail, ...] = (
    BypassAttemptGuardrail(),
)

OUTPUT_GUARDRAILS: tuple[Guardrail, ...] = (
    PrescriptionGuardrail(),
    DiagnosisGuardrail(),
    ClinicalDecisionGuardrail(),
    ScopeResidualGuardrail(),
)

ALL_GUARDRAILS: tuple[Guardrail, ...] = INPUT_GUARDRAILS + OUTPUT_GUARDRAILS


def list_guardrails() -> list[str]:
    """Lista os nomes de todos os guardrails registrados (útil pra CLI)."""
    return [g.name for g in ALL_GUARDRAILS]


# ────────────────────────────────────────────────────────────────────────
# Execução (sem ação — só detecção)
# ────────────────────────────────────────────────────────────────────────

def _run(guardrails: Iterable[Guardrail], text: str) -> list[GuardrailResult]:
    results: list[GuardrailResult] = []
    for g in guardrails:
        try:
            r = g.detect(text)
            results.append(r)
        except Exception as e:  # noqa: BLE001 — guardrail não pode crashar o grafo
            logger.exception("[%s] erro durante detect()", g.name)
            results.append(GuardrailResult(
                guardrail_name=g.name,
                triggered=False,
                level=g.level,
                applies_to=g.applies_to,
                matched_patterns=[],
                severity=0.0,
                message=f"erro interno: {e!s}",
            ))
    return results


def run_input_guardrails(question: str) -> list[GuardrailResult]:
    """Roda todos os input-side guardrails sobre a pergunta original."""
    return _run(INPUT_GUARDRAILS, question)


def run_output_guardrails(draft: str) -> list[GuardrailResult]:
    """Roda todos os output-side guardrails sobre o draft do LLM."""
    return _run(OUTPUT_GUARDRAILS, draft)


# ────────────────────────────────────────────────────────────────────────
# Aplicação de ação (rewrite via LLM ou nota anexada)
# ────────────────────────────────────────────────────────────────────────

def _build_combined_rewrite_prompt(
    draft: str,
    triggered_blocks: list[tuple[Guardrail, GuardrailResult]],
) -> str:
    """Constrói UM prompt de rewrite endereçando todos os blocks que dispararam.

    Pega o `rewrite_prompt` do PRIMEIRO guardrail (mais "técnico") como base,
    mas anexa contexto dos outros.
    """
    primary_g, primary_r = triggered_blocks[0]
    base = primary_g.rewrite_prompt(draft, primary_r)
    if len(triggered_blocks) == 1:
        return base

    # Anexa contexto dos outros guardrails detectados
    extra_lines = ["\n\nATENÇÃO — também ajustar para corrigir:"]
    for g, r in triggered_blocks[1:]:
        extra_lines.append(f"- [{g.name}] {r.message}")

    # Injetar antes do bloco "=== TEXTO ORIGINAL ==="
    marker = "=== TEXTO ORIGINAL ==="
    if marker in base:
        head, _, tail = base.partition(marker)
        return head + "\n".join(extra_lines) + "\n\n" + marker + tail
    # Fallback: append no final do prompt antes do texto
    return base + "\n".join(extra_lines)


def apply_guardrails_to_response(
    draft: str,
    llm: BaseChatModel,
) -> tuple[str, list[GuardrailResult], bool]:
    """Aplica TODOS os output-side guardrails ao draft e devolve a versão final.

    Lógica:
    1. Roda detect() em todos os output guardrails.
    2. Coleta os triggered.
    3. Se algum BLOCK disparou:
       - Constrói prompt combinado e chama LLM para reescrever.
       - Marca esses results com action_taken="rewritten".
    4. Se algum WARNING disparou:
       - Anexa a nota correspondente ao texto (uma vez por warning único).
       - Marca esses results com action_taken="note_appended".
    5. Devolve (texto_final, todos os results, foi_reescrito).

    Erros internos do LLM são capturados — devolve o draft original em
    caso de falha, marca action_taken="rewrite_failed".
    """
    results = run_output_guardrails(draft)

    triggered_blocks: list[tuple[Guardrail, GuardrailResult]] = []
    triggered_warnings: list[tuple[Guardrail, GuardrailResult]] = []
    for g, r in zip(OUTPUT_GUARDRAILS, results):
        if not r.triggered:
            continue
        if r.level == "block":
            triggered_blocks.append((g, r))
        elif r.level == "warning":
            triggered_warnings.append((g, r))

    text = draft
    was_rewritten = False

    # ─── Rewrite (uma chamada combinada) ────────────────────────────────
    if triggered_blocks:
        try:
            prompt = _build_combined_rewrite_prompt(text, triggered_blocks)
            messages = [HumanMessage(content=prompt)]
            response = llm.invoke(messages)
            text = (response.content if hasattr(response, "content") else str(response)).strip()
            was_rewritten = True
            for _, r in triggered_blocks:
                r.action_taken = "rewritten"
            logger.info(
                "Guardrails rewrite: %d block(s) → %d chars",
                len(triggered_blocks), len(text),
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Falha no rewrite via LLM")
            for _, r in triggered_blocks:
                r.action_taken = f"rewrite_failed: {e!s}"
            # Mantém o draft original — não substitui por erro

    # ─── Warnings (anexa nota) ──────────────────────────────────────────
    if triggered_warnings:
        for g, r in triggered_warnings:
            if isinstance(g, ScopeResidualGuardrail):
                # Evita duplicar a nota se já está no texto
                if SCOPE_NOTE.strip() not in text:
                    text = text + SCOPE_NOTE
                r.action_taken = "note_appended"
            else:
                # Outros warnings futuros: usar a mensagem padrão
                note = f"\n\n*Nota ({g.name}): {r.message}*"
                if note.strip() not in text:
                    text = text + note
                r.action_taken = "note_appended"

    return text, results, was_rewritten
