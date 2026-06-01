"""Classe abstrata `Guardrail` + dataclass `GuardrailResult` (Fase 6).

Cada guardrail é uma subclasse concreta com:
- `name`: identificador snake_case usado em logs e no audit DB
- `level`: "warning" (passa com nota anexa) ou "block" (reescreve / recusa)
- `applies_to`: "input" (sobre a pergunta do usuário) ou "output" (sobre o draft)
- `detect(text)`: retorna um `GuardrailResult`
- `rewrite_prompt(text, result)`: instrução pro LLM reescrever (só pros block + output)

Filosofia: falsos positivos são preferíveis a falsos negativos em contexto
clínico. Cada subclasse deve ter docstring com a razão CLÍNICA (não só técnica)
do que o guardrail protege.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

GuardrailLevel = Literal["warning", "block"]
GuardrailSide = Literal["input", "output"]


@dataclass
class GuardrailResult:
    """Resultado da inspeção de UM guardrail sobre UM texto.

    Sempre retornado por `detect`, mesmo quando não dispara — o resto do
    sistema usa `triggered` pra decidir.
    """

    guardrail_name: str
    triggered: bool
    level: GuardrailLevel = "block"
    applies_to: GuardrailSide = "output"
    matched_patterns: list[str] = field(default_factory=list)
    severity: float = 0.0       # 0.0 a 1.0 — útil pra audit + priorização
    message: str = ""           # mensagem curta pra log (visível no audit)
    # Preenchido depois pelo registry quando o action for tomado (rewrite ou note)
    action_taken: str | None = None

    def to_dict(self) -> dict:
        return {
            "guardrail_name": self.guardrail_name,
            "triggered": self.triggered,
            "level": self.level,
            "applies_to": self.applies_to,
            "matched_patterns": list(self.matched_patterns),
            "severity": self.severity,
            "message": self.message,
            "action_taken": self.action_taken,
        }


class Guardrail(ABC):
    """Classe base abstrata pros 5 guardrails da Fase 6."""

    # Subclasses DEVEM definir esses atributos de classe.
    name: str = ""
    level: GuardrailLevel = "block"
    applies_to: GuardrailSide = "output"

    @abstractmethod
    def detect(self, text: str) -> GuardrailResult:
        """Aplica os padrões e devolve um `GuardrailResult`."""
        raise NotImplementedError

    def rewrite_prompt(self, original_text: str, result: GuardrailResult) -> str:
        """Instrução pro LLM reescrever quando o guardrail é `block + output`.

        Override nas subclasses pra mensagens específicas por categoria.
        Default (uso pelos guardrails input-side ou warning) é genérico.
        """
        return (
            f"O texto abaixo violou a regra '{self.name}'. "
            f"Reescreva removendo o padrão problemático ('{result.message}'), "
            f"preservando o conteúdo técnico útil e o português brasileiro formal.\n\n"
            f"=== TEXTO ORIGINAL ===\n{original_text}\n\n"
            f"=== TEXTO REESCRITO ===\n"
        )

    def _make_result(
        self,
        triggered: bool,
        matched: list[str] | None = None,
        severity: float = 0.0,
        message: str = "",
    ) -> GuardrailResult:
        """Helper pra subclasses: cria o GuardrailResult com defaults da classe."""
        return GuardrailResult(
            guardrail_name=self.name,
            triggered=triggered,
            level=self.level,
            applies_to=self.applies_to,
            matched_patterns=matched or [],
            severity=severity,
            message=message,
        )

    def __repr__(self) -> str:
        return f"<Guardrail {self.name} level={self.level} side={self.applies_to}>"
