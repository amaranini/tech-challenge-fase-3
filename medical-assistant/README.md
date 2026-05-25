# medical-assistant

Assistente médico construído como Tech Challenge da pós-graduação (Fase 3).
Combina um **LLM fine-tuned com dados médicos**, **LangChain** para
orquestração, **LangGraph** para fluxos de decisão e **guardrails** para
segurança e auditoria.

> ⚠️ Projeto acadêmico. **Não substitui orientação médica profissional.**

---

## Sobre o Projeto

O objetivo é demonstrar, ponta-a-ponta, como construir um assistente de
domínio especializado a partir de um modelo de linguagem de propósito geral:

1. **Fine-tuning** de um modelo base (Qwen2.5-3B-Instruct) com dados
   médicos públicos, executado em GPU remota (Google Colab).
2. **Inferência local** no Mac Apple Silicon usando MLX (ou Ollama como
   fallback), sem depender de APIs pagas.
3. **Orquestração** com LangChain (cadeias, prompts, parsers) e
   **LangGraph** (grafos de decisão com estado, p.ex. "consultar base
   antes de responder").
4. **RAG** (Retrieval-Augmented Generation — recuperar contexto antes de
   gerar) sobre uma base vetorial Chroma com embeddings de
   `sentence-transformers`.
5. **Guardrails**: filtros de entrada/saída, prompts defensivos,
   verificação de claims e **log de auditoria** de toda interação.
6. **Interface**: API FastAPI + frontend Streamlit para a demonstração.

---

## Arquitetura

```mermaid
flowchart LR
    U[Usuário] -->|pergunta| UI[UI Streamlit]
    UI -->|HTTP| API[API FastAPI]
    API --> GRAPH[Agente LangGraph]

    subgraph AGENT[Camada do Agente]
        GRAPH --> GUARD_IN[Guardrail de entrada]
        GUARD_IN --> ROUTER{Roteador}
        ROUTER -->|consulta base| RAG[(Vector DB - Chroma)]
        ROUTER -->|ferramenta| TOOLS[Tools: lookup, calc, etc]
        ROUTER -->|geração| LLM[LLM local - MLX/Ollama]
        RAG --> LLM
        TOOLS --> LLM
        LLM --> GUARD_OUT[Guardrail de saída]
    end

    GUARD_OUT --> API
    API -->|resposta| UI
    UI --> U

    GRAPH -.->|log auditoria| LOG[(logging_/logs)]
```

**Leitura rápida:** o usuário interage com a UI; cada pergunta passa por
um guardrail de entrada, é roteada pelo LangGraph para consultar a base
vetorial e/ou ferramentas, gera uma resposta no LLM local, passa por um
guardrail de saída e é registrada em log de auditoria.

---

## Como Rodar

> **TODO** — será preenchido na Fase 1, quando o ambiente Python estiver
> configurado com `uv` e tivermos um primeiro "hello world" do LangChain.

Resumo do que estará aqui:
- Instalação do `uv`.
- `uv sync` para instalar dependências.
- Download do modelo (MLX ou Ollama).
- Subir API (`uvicorn`) + UI (`streamlit`).

---

## Estrutura de Pastas

```
medical-assistant/
├── README.md              ← este arquivo
├── DECISIONS.md           ← log de decisões técnicas (leia para entender o "porquê")
├── pyproject.toml         ← dependências e config do projeto
├── .env.example           ← variáveis de ambiente (copiar para .env)
├── .gitignore
├── data/
│   ├── raw/               ← datasets crus baixados (não vai pro git)
│   ├── synthetic/         ← dados gerados artificialmente
│   └── processed/         ← datasets limpos prontos pra treino
├── finetuning/
│   └── configs/           ← YAMLs com hiperparâmetros do treino (Colab)
├── assistant/
│   └── tools/             ← ferramentas que o agente pode chamar
├── api/                   ← backend FastAPI
├── ui/                    ← frontend Streamlit
├── logging_/
│   └── logs/              ← logs de auditoria (não vai pro git)
├── evaluation/            ← scripts de avaliação do modelo
├── docs/                  ← documentação técnica complementar
└── notebooks/             ← notebooks Jupyter (inclui o de treino do Colab)
```

> O `_` em `logging_/` evita conflito com o módulo `logging` da biblioteca
> padrão do Python.
