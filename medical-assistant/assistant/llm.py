"""MedicalLLM — wrapper LangChain do modelo médico fine-tuned (mlx-lm).

Implementa `BaseChatModel` para que o modelo Qwen2.5-1.5B + adapter LoRA
seja usável em qualquer chain do LangChain (`.invoke`, `.batch`,
`StrOutputParser`, `RunnableSequence`, etc).

Características importantes:
- **Lazy load + cache**: modelo só carrega na 1ª chamada de `_generate`.
  Permite instanciar várias vezes (em testes) sem custo de memória.
- **System prompt configurável** na instância ou via `SystemMessage` no
  input. Convenção: se a lista de mensagens já contém um `SystemMessage`,
  o do usuário ganha; senão, o `self.system_prompt` é prepended.
- **Erro claro** se `adapter_path` foi informado mas o caminho não existe.
- **Sync only por enquanto**: `_stream`, `_agenerate`, `_astream` não estão
  implementados. Podem ser adicionados na Fase 6 (UI) usando
  `mlx_lm.stream_generate`.

Exemplo de uso:

    from assistant import MedicalLLM, MEDICAL_SYSTEM_PROMPT, build_default_llm

    # Forma curta — paths default do .env + system prompt clínico.
    llm = build_default_llm()
    resp = llm.invoke("Quais são os critérios de SIRS?")

    # Forma explícita.
    llm = MedicalLLM(
        model_path="mlx-community/Qwen2.5-1.5B-Instruct-bf16",
        adapter_path="./finetuning/output/adapters",
        system_prompt=MEDICAL_SYSTEM_PROMPT,
        temperature=0.3,
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr

logger = logging.getLogger(__name__)

# ─── Defaults ───────────────────────────────────────────────────────────────
# Temperature 0.3 é deliberadamente baixa: em contexto clínico queremos
# respostas consistentes, não "criativas". 0.0 seria determinístico (greedy);
# 0.3 mantém alguma diversidade útil pra reformular respostas parecidas
# sem virar alucinação.
_DEFAULT_TEMP = 0.3
_DEFAULT_MAX_TOKENS = 512
_DEFAULT_TOP_P = 0.95


def _messages_to_chat_format(
    messages: list[BaseMessage],
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    """Converte mensagens LangChain → formato esperado pelo Qwen2.5.

    - Se `system_prompt` for fornecido E não houver SystemMessage no input,
      prepend o system_prompt no início.
    - Se o input já tem SystemMessage, respeita o do usuário (princípio:
      chain do usuário ganha do default da instância).
    """
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    result: list[dict[str, str]] = []

    if system_prompt and not has_system:
        result.append({"role": "system", "content": system_prompt})

    for m in messages:
        if isinstance(m, SystemMessage):
            result.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            result.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            result.append({"role": "assistant", "content": m.content})
        else:
            raise ValueError(
                f"Tipo de mensagem não suportado: {type(m).__name__}. "
                f"Use SystemMessage, HumanMessage ou AIMessage."
            )
    return result


class MedicalLLM(BaseChatModel):
    """Modelo médico fine-tuned + LoRA, integrado ao LangChain via mlx-lm."""

    model_path: str = Field(..., description="Path/ID do modelo base (HF ou local).")
    adapter_path: Optional[str] = Field(
        None, description="Path do adapter LoRA. None = só o modelo base."
    )
    system_prompt: Optional[str] = Field(
        None, description="System prompt default aplicado quando não vem no input."
    )
    temperature: float = Field(_DEFAULT_TEMP, ge=0.0, le=2.0)
    max_tokens: int = Field(_DEFAULT_MAX_TOKENS, gt=0)
    top_p: float = Field(_DEFAULT_TOP_P, gt=0.0, le=1.0)

    # Estado interno — não serializa nem aparece em `_identifying_params`.
    _model: Any = PrivateAttr(default=None)
    _tokenizer: Any = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        return "medical-mlx-lora"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "adapter_path": self.adapter_path,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "has_system_prompt": self.system_prompt is not None,
        }

    def _ensure_loaded(self) -> None:
        """Carrega o modelo + adapter na primeira chamada e cacheia."""
        if self._model is not None:
            return

        if self.adapter_path:
            adapter = Path(self.adapter_path).expanduser().resolve()
            if not adapter.exists():
                raise FileNotFoundError(
                    f"Adapter LoRA não encontrado em '{adapter}'.\n"
                    f"Como resolver:\n"
                    f"  1) Treinar: uv run python finetuning/train.py\n"
                    f"  2) Ou ajustar `adapter_path` no construtor do MedicalLLM."
                )

        logger.info(
            "Carregando modelo (%s) %s",
            self.model_path,
            f"+ adapter {self.adapter_path}" if self.adapter_path else "(sem adapter)",
        )
        from mlx_lm import load

        if self.adapter_path:
            self._model, self._tokenizer = load(
                self.model_path, adapter_path=self.adapter_path
            )
        else:
            self._model, self._tokenizer = load(self.model_path)
        logger.info("Modelo carregado.")

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._ensure_loaded()

        chat_messages = _messages_to_chat_format(messages, self.system_prompt)
        prompt = self._tokenizer.apply_chat_template(
            chat_messages, tokenize=False, add_generation_prompt=True
        )

        logger.debug("Generating with %d messages", len(chat_messages))

        # mlx-lm: sampler controla temperature/top_p; max_tokens vai direto.
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        sampler = make_sampler(temp=self.temperature, top_p=self.top_p)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        text = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

        # Stop sequences manuais (mlx-lm não tem suporte nativo).
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
                    break

        ai_message = AIMessage(content=text.strip())
        return ChatResult(generations=[ChatGeneration(message=ai_message)])


def build_default_llm() -> MedicalLLM:
    """Constrói o MedicalLLM com paths e defaults do `.env` + system prompt clínico."""
    from assistant.config import (
        ADAPTER_PATH,
        DEFAULT_MAX_TOKENS,
        DEFAULT_TEMPERATURE,
        DEFAULT_TOP_P,
        MODEL_PATH,
    )
    from assistant.prompts import MEDICAL_SYSTEM_PROMPT

    return MedicalLLM(
        model_path=MODEL_PATH,
        adapter_path=ADAPTER_PATH,
        system_prompt=MEDICAL_SYSTEM_PROMPT,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
        top_p=DEFAULT_TOP_P,
    )
