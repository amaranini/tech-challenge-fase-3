"""Pacote `assistant` — wrapper LangChain do modelo médico fine-tuned + utilitários."""

from assistant.llm import MedicalLLM, build_default_llm
from assistant.prompts import (
    MEDICAL_SYSTEM_PROMPT,
    MEDICAL_SYSTEM_PROMPT_STRICT,
    get_system_prompt,
)

__all__ = [
    "MedicalLLM",
    "build_default_llm",
    "MEDICAL_SYSTEM_PROMPT",
    "MEDICAL_SYSTEM_PROMPT_STRICT",
    "get_system_prompt",
]
