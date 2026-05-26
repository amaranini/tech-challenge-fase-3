# `assistant/` — wrapper LangChain do modelo médico

Esta pasta contém o **`MedicalLLM`**, classe que adapta o modelo fine-tuned
(Qwen2.5-1.5B + adapter LoRA, treinado na Fase 2) para a interface de
`BaseChatModel` do LangChain. Com isso, o modelo pode ser usado em
qualquer chain do LangChain (`.invoke`, `.batch`, `RunnableSequence`, etc.)
da mesma forma que se usaria um modelo da OpenAI ou Anthropic.

---

## Arquivos

| Arquivo | Função |
|---|---|
| `llm.py` | Classe `MedicalLLM` + função `build_default_llm()` |
| `prompts.py` | `MEDICAL_SYSTEM_PROMPT` (default) e `MEDICAL_SYSTEM_PROMPT_STRICT` (Fase 6) |
| `config.py` | Lê `.env` e expõe `MODEL_PATH`, `ADAPTER_PATH`, defaults |
| `test_llm.py` | 8 testes rápidos + 2 lentos (marcados `slow`) |
| `demo_chat.py` | CLI interativo (rich) com `/system`, `/clear`, `/exit` |

---

## Como usar

### Forma curta (recomendado)

```python
from assistant import build_default_llm

llm = build_default_llm()  # lê paths do .env, aplica system prompt clínico
resp = llm.invoke("Quais critérios fecham diagnóstico de SIRS?")
print(resp.content)
```

### Forma explícita

```python
from assistant import MedicalLLM, MEDICAL_SYSTEM_PROMPT

llm = MedicalLLM(
    model_path="mlx-community/Qwen2.5-1.5B-Instruct-bf16",
    adapter_path="./finetuning/output/adapters",
    system_prompt=MEDICAL_SYSTEM_PROMPT,
    temperature=0.3,
    max_tokens=512,
)
resp = llm.invoke("Resuma o protocolo de sepse.")
```

### Em uma chain LangChain

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from assistant import build_default_llm

llm = build_default_llm()
prompt = ChatPromptTemplate.from_messages([
    ("human", "Em uma frase: {pergunta}"),
])
chain = prompt | llm | StrOutputParser()
print(chain.invoke({"pergunta": "o que é diabetes tipo 2?"}))
```

---

## Demo chat interativo

```bash
uv run python assistant/demo_chat.py
```

Comandos dentro do REPL:
- `/exit` — encerrar.
- `/clear` — limpar histórico (mantém system prompt).
- `/system "Responda apenas em emojis."` — trocar system prompt ao vivo
  (útil pro vídeo: comparar mesmo modelo com prompts clínicos vs lazy).

Flags:
- `--show-system` — exibe o system prompt ativo no banner inicial.
- `--base` — roda **sem** system prompt clínico (pra comparar).

---

## Testes

```bash
uv run pytest assistant/ -v -m "not slow"   # 8 rápidos, <1s
uv run pytest assistant/ -v -m slow         # 2 lentos, carrega modelo (~1 min)
uv run pytest assistant/ -v                 # todos
```

---

## Convenções importantes da classe

- **Lazy load**: o modelo só é carregado na primeira chamada de
  `.invoke()` / `.batch()` / `_generate()`. Você pode construir várias
  instâncias em testes sem custo de memória.
- **System prompt**: se a instância tem `system_prompt` E você chamar
  `.invoke()` sem nenhuma `SystemMessage`, o system prompt da instância é
  prepended. Se você passar uma `SystemMessage`, ela ganha (princípio:
  chain do usuário > default da instância).
- **Erro de adapter**: se `adapter_path` foi informado mas o caminho não
  existe no filesystem, `_ensure_loaded()` levanta `FileNotFoundError`
  com instrução em PT-BR de como resolver.
- **Não implementado ainda**: streaming (`_stream`), async
  (`_agenerate`/`_astream`). Podem ser adicionados na Fase 6 (UI) com
  `mlx_lm.stream_generate` sem refazer a classe.
