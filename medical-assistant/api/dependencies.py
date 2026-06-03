"""Dependency injection da API (Fase 7).

Mantém aqui:
- `require_doctor_id`     — extrai/valida o header `X-Doctor-Id`
- `get_audit_reader`      — singleton do AuditReader (read-only)
- `run_graph_callable`    — função que executa o grafo (substituível em testes)

A substituição em testes é via `app.dependency_overrides[run_graph_callable] = ...`,
sem mockar imports do módulo `assistant.graph`.

REGRA: o modelo carrega 1x no startup (em api/server.py via lifespan). Aqui só
mantemos handles — nada que toque modelo.
"""

from __future__ import annotations

import logging
from typing import Annotated, Callable, Optional

from fastapi import Header, HTTPException

from assistant.audit.reader import AuditReader
from assistant.graph import run_medical_graph
from assistant.graph_state import MedicalState

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────
# X-Doctor-Id — autenticação simulada
# ────────────────────────────────────────────────────────────────────────

def require_doctor_id(
    x_doctor_id: Annotated[
        Optional[str],
        Header(alias="X-Doctor-Id", description="Identificador do médico"),
    ] = None,
) -> str:
    """Exige header X-Doctor-Id em endpoints com side effect.

    Autenticação real está fora de escopo nesta fase — usamos uma string
    livre só pra demonstrar que o sistema rastreia QUEM consultou. A string
    é gravada em `interactions.doctor_id` no audit DB.

    Levanta 400 se ausente ou vazio.
    """
    if not x_doctor_id or not x_doctor_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Header 'X-Doctor-Id' obrigatório (ex: 'DR_SILVA').",
        )
    return x_doctor_id.strip()


# ────────────────────────────────────────────────────────────────────────
# AuditReader
# ────────────────────────────────────────────────────────────────────────

_AUDIT_READER_SINGLETON: AuditReader | None = None


def get_audit_reader() -> AuditReader:
    """Singleton do AuditReader. Cada chamada de método abre/fecha conexão."""
    global _AUDIT_READER_SINGLETON
    if _AUDIT_READER_SINGLETON is None:
        _AUDIT_READER_SINGLETON = AuditReader()
    return _AUDIT_READER_SINGLETON


# ────────────────────────────────────────────────────────────────────────
# Runner do grafo (callable injectable)
# ────────────────────────────────────────────────────────────────────────

GraphRunner = Callable[[str, Optional[str], Optional[str]], MedicalState]


def run_graph_callable() -> GraphRunner:
    """Devolve a função que executa o grafo. Substituível em testes via
    `app.dependency_overrides`.
    """
    return run_medical_graph
