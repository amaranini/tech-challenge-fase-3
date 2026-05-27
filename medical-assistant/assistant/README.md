# `assistant/` — wrapper LangChain + RAG + tool de prontuário + grafo LangGraph

Esta pasta contém:

- **`MedicalLLM`** (Fase 3) — wrapper `BaseChatModel` do modelo
  fine-tuned (Qwen2.5-1.5B + adapter LoRA).
- **RAG** (Fase 4) — Chroma + sentence-transformers indexando os
  protocolos sintéticos, com retriever pluggável.
- **Tool de prontuário** (Fase 4) — SQLite com os 50 pacientes
  sintéticos, função `get_patient_by_id`.
- **Roteador determinístico + chain** (Fase 4) — regex decide o que
  acionar; `build_medical_chain` orquestra tudo via LangChain. (Mantida
  como referência; o orquestrador oficial agora é o grafo.)
- **Grafo LangGraph** (Fase 5) — 9 nós + refuse + rewrite, com estado
  compartilhado, logging por nó e diagrama exportável. `run_medical_graph`
  é a nova interface principal.

---

## Arquivos

| Arquivo | Função |
|---|---|
| `llm.py` | Classe `MedicalLLM` + função `build_default_llm()` |
| `prompts.py` | `MEDICAL_SYSTEM_PROMPT` (default) e `MEDICAL_SYSTEM_PROMPT_STRICT` (Fase 6) |
| `config.py` | Lê `.env` e expõe `MODEL_PATH`, `ADAPTER_PATH`, defaults |
| `router.py` | `route(query) → RoutingDecision`: regex `P\d{4}` decide tool de paciente |
| `chain.py` | `build_medical_chain(llm, retriever, lookup, ...)` e `build_default_chain()` |
| `rag/build_index.py` | Lê protocolos, chunka, embeda, persiste em Chroma |
| `rag/retriever.py` | `ProtocolRetriever.retrieve(query, top_k)` |
| `tools/build_patient_db.py` | CSV → SQLite |
| `tools/patient_records.py` | `get_patient_by_id` + dataclass `PatientRecord` |
| `test_llm.py` | 8 unit + 2 slow (modelo real) |
| `test_router.py` | 8 unit do roteador |
| `test_chain.py` | 6 integração com mocks |
| `test_rag.py` | 4 do retriever (pulam se índice não existir) |
| `demo_chat.py` | CLI Fase 4 (chain) com `/sources`, `/no-rag` |
| `graph_state.py` | **Fase 5**: `MedicalState` TypedDict + reducers acumulativos |
| `graph_prompts.py` | **Fase 5**: prompts dos nós (triage, generate, rewrite, refuse) |
| `intent_classifier.py` | **Fase 5**: classificador determinístico do Nó 1 (keyword) |
| `graph_nodes.py` | **Fase 5**: 9 nós + refuse + rewrite, todos defensivos |
| `graph.py` | **Fase 5**: `build_graph()`, `run_medical_graph()`, `export_diagram()` |
| `demo_graph.py` | **Fase 5**: CLI do grafo com `/trace`, `/state`, `/alerts` |
| `test_graph_nodes.py` | **Fase 5**: 42 unit tests do grafo (~1s) |
| `test_graph_integration.py` | **Fase 5**: 3 end-to-end com modelo real (slow) |
| `test_classifier_prompts.py` | **Fase 5**: validação manual dos prompts (não-pytest) |

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

## Como construir o índice RAG

```bash
uv run python assistant/rag/build_index.py
```

> Lê todos os `.md` de `data/synthetic/protocols/`, divide em chunks
> (~400 tokens, overlap 80), gera embeddings com
> `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` e
> persiste em `assistant/data/chroma_db/`. Idempotente: deleta a coleção
> anterior antes de recriar.
>
> Tempo: ~30-90s (primeira vez baixa ~120 MB do modelo de embeddings).
> Saída esperada: ~30-40 protocolos → ~80-150 chunks indexados.

**Smoke test** (lê um trecho relevante):

```bash
uv run python -m assistant.rag.retriever "Como manejar sepse?"
```

## Como construir o banco de pacientes

```bash
uv run python assistant/tools/build_patient_db.py
```

> Lê `data/synthetic/patients.csv`, calcula idade a partir da data de
> nascimento, popula `assistant/data/patients.db` com schema fixo.
> Idempotente (drop & recreate). Saída: ~50 pacientes carregados.

**Smoke test:**

```bash
uv run python -m assistant.tools.patient_records P0001    # encontra
uv run python -m assistant.tools.patient_records P9999    # gracefully
```

## Fluxo automatizado (LangGraph — Fase 5)

A Fase 5 substitui o orquestrador da Fase 4 por um grafo de estado com
9 nós + 2 auxiliares (refuse, rewrite). O grafo é a interface principal
do assistente agora; a chain LangChain da Fase 4 continua existindo como
referência.

### Smoke test e diagrama

```bash
# Compila o grafo, exporta diagrama (Mermaid + PNG), e roda 1 query
uv run python assistant/graph.py
```

Saídas:
- `docs/langgraph_flow_auto.md` — Mermaid gerado pelo LangGraph
- `docs/langgraph_flow.png` — PNG via mermaid.ink (requer rede)
- `docs/langgraph_flow.md` — versão escrita à mão (mais legível)

### Uso programático

```python
from assistant.graph import run_medical_graph

state = run_medical_graph(
    question="Paciente em sepse grave com PA 70x40, conduta?",
    patient_id="P0001",
)

print(state["final_response"])
print("Intent:", state["intent"])           # clinica
print("Urgency:", state["urgency"])         # alta
print("Trace:", len(state["node_trace"]))   # ~9
print("Alertas emitidos:", state["alerts_emitted"])
```

### Demo interativo do grafo

```bash
uv run python assistant/demo_graph.py
```

A cada pergunta, cada nó aparece executando em tempo real:

```
🎯 classify_intent       clinica (kw='paciente')
🚦 triage_urgency        raw='alta' → alta
👤 fetch_patient_data    P0001 (argumento) → Apollo Sousa, 5a
🧪 check_pending_exams   P0001 → 1 exame(s) pendente(s)
📚 retrieve_protocol     3 chunk(s), scores=[0.82, 0.75, 0.62]
💭 generate_response     264 chars: 'Resposta...'
🛡️ guardrail_check        sem flags
🚨 emit_alert_if_needed  ALERTA emitido pid=P0001
✅ finalize_response      final=545 chars
```

Comandos:
- `/trace` — tabela com nós executados na última pergunta
- `/state` — JSON do estado completo
- `/alerts` — alertas emitidos NESTA sessão
- `/clear` — limpa a tela
- `/exit` — sai

### Avaliação automatizada

```bash
uv run python evaluation/eval_graph.py
cat evaluation/graph_eval_results.md
```

> 10 casos cobrindo os principais ramos do grafo (fora de escopo,
> urgência alta, paciente + protocolo, só protocolo, guardrail
> dispara, paciente inexistente). Resultado atual: **10/10**.
> Saídas detalhadas em `evaluation/graph_traces/case_NN.json`.

### Logs estruturados

- `logging_/alerts.jsonl` — 1 linha por alerta de urgência alta
- `logging_/graph_traces.jsonl` — 1 linha por execução completa

---

## Demo chat (Fase 4, ainda funcional)

```bash
uv run python assistant/demo_chat.py
```

Comandos dentro do REPL:
- `/exit` — encerrar.
- `/clear` — limpar last_sources.
- `/sources` — mostrar fontes da última resposta em detalhe.
- `/no-rag` — desligar RAG só na próxima pergunta (toggle).
- `/system "novo prompt"` — trocar system prompt ao vivo.

Flags:
- `--show-system` — exibe o system prompt no banner inicial.
- `--base` — roda **sem** system prompt clínico.
- `--no-rag` — inicia com RAG já desligado.

Exemplo de fluxo (ótimo pro vídeo):
1. `Qual o protocolo de sepse?` → indicador 📚, resposta + tabela de fontes.
2. `Quais as alergias do P0042?` → indicador 👤, resposta usando dados reais do banco.
3. `Para o paciente P0007 com pneumonia, qual conduta?` → 📚 + 👤 combinados.
4. `/sources` → painel detalhado das fontes da última resposta.
5. `/no-rag` + repete a pergunta 1 → comportamento diferente (sem contexto).

---

## Avaliação automatizada

```bash
uv run python evaluation/eval_rag.py
cat evaluation/comparison_phase4.md
```

> Roda 15 casos (5 só-RAG, 3 só-paciente, 3 ambos, 2 fora-de-escopo, 2 ID
> inexistente). Calcula % de roteamento correto e latências médias.
> Gera `evaluation/comparison_phase4.md` com fontes e respostas
> lado-a-lado (entregável pro relatório e vídeo).

## Testes

```bash
uv run pytest assistant/ -v -m "not slow"   # ~60 rápidos: ~2s
uv run pytest assistant/ -v -m slow         # 5 lentos: carrega modelo (~1 min)
uv run pytest assistant/ -v                 # todos
```

> Fase 5 adicionou 42 unit tests em `test_graph_nodes.py` + 3 slow em
> `test_graph_integration.py`. Veja a [arquitetura da Fase 5](../docs/arquitetura_fase5.md)
> para o diagrama completo do grafo.

> Os 4 testes do retriever (`test_rag.py`) pulam automaticamente se o
> índice em `assistant/data/chroma_db/` não tiver sido construído.

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
