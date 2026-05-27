"""Roteador determinístico — decide quais "ferramentas" cada pergunta dispara.

Sem tool calling nativo do LLM: a decisão é tomada por regex + heurísticas
simples, ANTES de chamar o modelo. Mais previsível e auditável que confiar
no Qwen 1.5B pra decidir o que chamar.

Regras atuais:
- **RAG sempre ativo** (sempre tenta recuperar contexto dos protocolos).
- **Busca de paciente** acionada quando o regex `\\bP\\d{4}\\b` casa com o
  texto da pergunta (formato exato dos IDs em `data/synthetic/patients.csv`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PATIENT_ID_RE = re.compile(r"\bP\d{4}\b")


@dataclass
class RoutingDecision:
    needs_rag: bool
    needs_patient: bool
    patient_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "needs_rag": self.needs_rag,
            "needs_patient": self.needs_patient,
            "patient_ids": list(self.patient_ids),
        }


def route(query: str) -> RoutingDecision:
    """Analisa a pergunta e devolve a decisão de roteamento.

    Sempre marca `needs_rag=True` — quem decide se o contexto é útil é
    o threshold/score no retriever (ou o LLM ao ler o prompt). Aqui não
    descartamos a busca pra não cegar o LLM em perguntas ambíguas.
    """
    ids = list(dict.fromkeys(PATIENT_ID_RE.findall(query)))  # preserva ordem, deduplica
    return RoutingDecision(
        needs_rag=True,
        needs_patient=bool(ids),
        patient_ids=ids,
    )
