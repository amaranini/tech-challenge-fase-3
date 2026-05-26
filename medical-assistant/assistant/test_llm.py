"""Testes do MedicalLLM.

- Rápidos (sem `slow` marker): não carregam o modelo MLX. Rodam em < 1s.
- Lentos (`@pytest.mark.slow`): carregam o modelo real. Pulam por default.

Comandos:
    uv run pytest assistant/ -v -m "not slow"   # rápidos
    uv run pytest assistant/ -v -m slow         # lentos (~1 min)
    uv run pytest assistant/ -v                 # todos
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistant.llm import MedicalLLM, _messages_to_chat_format


# ─── Testes rápidos (não carregam modelo) ───────────────────────────────────


def test_instantiates_without_loading():
    """Construir não deve carregar o modelo (lazy load)."""
    llm = MedicalLLM(model_path="foo", adapter_path="bar")
    assert llm._model is None
    assert llm._tokenizer is None


def test_llm_type():
    llm = MedicalLLM(model_path="foo")
    assert llm._llm_type == "medical-mlx-lora"


def test_identifying_params():
    llm = MedicalLLM(
        model_path="foo", adapter_path="bar", temperature=0.5, system_prompt="oi"
    )
    params = llm._identifying_params
    assert params["model_path"] == "foo"
    assert params["adapter_path"] == "bar"
    assert params["temperature"] == 0.5
    assert params["max_tokens"] > 0
    assert params["has_system_prompt"] is True


def test_invalid_adapter_raises_on_invoke(tmp_path):
    """Adapter inexistente: instancia OK, mas invoke levanta erro claro."""
    nonexistent = tmp_path / "no_adapter_here"
    llm = MedicalLLM(model_path="foo", adapter_path=str(nonexistent))
    with pytest.raises(FileNotFoundError, match="Adapter LoRA não encontrado"):
        llm.invoke("teste")


def test_message_conversion_basic():
    messages = [
        SystemMessage(content="você é um teste"),
        HumanMessage(content="oi"),
        AIMessage(content="olá"),
        HumanMessage(content="tudo bem?"),
    ]
    result = _messages_to_chat_format(messages)
    assert result == [
        {"role": "system", "content": "você é um teste"},
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
        {"role": "user", "content": "tudo bem?"},
    ]


def test_message_conversion_prepends_default_system_prompt():
    """Se não houver SystemMessage no input, prepend o system_prompt da instância."""
    messages = [HumanMessage(content="oi")]
    result = _messages_to_chat_format(messages, system_prompt="default sys")
    assert result[0] == {"role": "system", "content": "default sys"}
    assert result[1] == {"role": "user", "content": "oi"}


def test_message_conversion_respects_user_system_message():
    """Se já tem SystemMessage no input, NÃO duplica com o default."""
    messages = [
        SystemMessage(content="user sys"),
        HumanMessage(content="oi"),
    ]
    result = _messages_to_chat_format(messages, system_prompt="default sys")
    assert len(result) == 2
    assert result[0]["content"] == "user sys"


def test_message_conversion_rejects_unknown_type():
    """Tipos não suportados levantam ValueError claro."""

    class FakeMessage(HumanMessage):
        pass

    # HumanMessage filho ainda passa pois isinstance(x, HumanMessage) é True.
    # Para garantir falha, monto um BaseMessage cru via classe não-conhecida.
    from langchain_core.messages import FunctionMessage

    messages = [FunctionMessage(name="fn", content="x")]
    with pytest.raises(ValueError, match="Tipo de mensagem não suportado"):
        _messages_to_chat_format(messages)


# ─── Testes lentos (carregam modelo real) ──────────────────────────────────


@pytest.mark.slow
def test_real_generation_loads_and_responds():
    """Carrega adapter real e gera resposta em PT-BR. ~30s primeira vez."""
    from assistant.llm import build_default_llm

    llm = build_default_llm()
    response = llm.invoke("Olá, o que você é?")
    text = response.content
    assert text, "Resposta vazia."
    assert len(text) > 10, f"Resposta muito curta: {text!r}"
    # Sinal mínimo de PT-BR: acentos ou palavras comuns.
    has_pt = any(c in text.lower() for c in "áéíóúâêôãõç") or any(
        w in text.lower() for w in ("assistente", "olá", "sou", "ajudar", "clínico", "médico")
    )
    assert has_pt, f"Resposta não parece PT-BR: {text[:200]!r}"


@pytest.mark.slow
def test_system_prompt_changes_behavior():
    """Mesma pergunta com vs sem system prompt restritivo → respostas diferem."""
    from assistant.config import ADAPTER_PATH, MODEL_PATH

    llm_terse = MedicalLLM(
        model_path=MODEL_PATH,
        adapter_path=ADAPTER_PATH,
        system_prompt="Responda em UMA palavra apenas, sem pontuação.",
        temperature=0.0,
        max_tokens=20,
    )
    llm_default = MedicalLLM(
        model_path=MODEL_PATH,
        adapter_path=ADAPTER_PATH,
        temperature=0.0,
        max_tokens=200,
    )
    pergunta = "O que é amoxicilina?"
    r_terse = llm_terse.invoke(pergunta).content.strip()
    r_default = llm_default.invoke(pergunta).content.strip()
    assert len(r_terse) < len(r_default), (
        f"Esperava resposta curta com system 'uma palavra'; "
        f"r_terse({len(r_terse)})={r_terse!r}, r_default({len(r_default)})={r_default!r}"
    )
