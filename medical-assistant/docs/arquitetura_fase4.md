# Arquitetura — Fase 4

Estado do sistema após a Fase 4: o assistente combina **fine-tuning local
(Fase 2)**, **system prompt clínico (Fase 3)** e agora **RAG + tool de
prontuário (Fase 4)**, orquestrados por uma chain LangChain com
**roteamento determinístico** (sem tool calling nativo do LLM).

---

## Fluxo de uma pergunta

```mermaid
flowchart TB
    U([Usuário]) -->|pergunta| DEMO[demo_chat.py / chain.invoke]

    DEMO --> ROUTER{Router<br/>regex + heurísticas<br/>assistant/router.py}

    ROUTER -->|sempre| RAG[ProtocolRetriever<br/>Chroma + sentence-transformers<br/>assistant/rag/retriever.py]
    ROUTER -->|se ID detectado<br/>regex \bP\\d{4}\b| TOOL[get_patient_by_id<br/>SQLite<br/>assistant/tools/patient_records.py]

    RAG -->|top_k=3 chunks<br/>+ metadata| PROMPT
    TOOL -->|PatientRecord<br/>ou None| PROMPT

    PROMPT[Prompt enriquecido<br/>system + contexto + paciente + pergunta]
    PROMPT --> LLM[MedicalLLM<br/>Qwen2.5-1.5B + adapter LoRA<br/>via mlx-lm + LangChain]
    LLM -->|resposta texto| MERGE[Anexa fontes<br/>programaticamente<br/>Estratégia B]
    MERGE -->|dict completo| DEMO

    DEMO -->|response<br/>+ sources<br/>+ patient_data<br/>+ latencies| U

    subgraph DADOS[Dados persistidos]
        CHROMA[(Chroma<br/>assistant/data/chroma_db/)]
        SQLITE[(SQLite<br/>assistant/data/patients.db)]
        ADAPTER[(LoRA adapter<br/>finetuning/output/adapters/)]
    end

    RAG -.lê.-> CHROMA
    TOOL -.lê.-> SQLITE
    LLM -.lê.-> ADAPTER
```

---

## Decisões-chave da fase

| Decisão | Por quê | Onde |
|---|---|---|
| **Sem tool calling nativo** | Qwen 1.5B não confiável pra escolher tool; roteador determinístico via regex é mais auditável | `assistant/router.py` |
| **Embedding multilíngue leve** | `paraphrase-multilingual-MiniLM-L12-v2` cobre PT-BR, ~120MB, roda rápido no M1 | `assistant/rag/build_index.py` |
| **Chunking ~400 tokens header-first** | Captura "uma seção típica" de protocolo; overlap 80 evita perder frases na borda | `RecursiveCharacterTextSplitter.from_tiktoken_encoder` |
| **Sem threshold rígido** | Sempre devolve top_k=3; prompt instrui o LLM a usar contexto SE relevante. Evita "cegar" o modelo em perguntas ambíguas | `ProtocolRetriever.retrieve` |
| **Fontes anexadas programaticamente (Estratégia B)** | Modelo pequeno alucina nomes de arquivos; metadados do Chroma são fonte da verdade | `chain.py` retorna `sources: list[dict]` |
| **SQLite, não Postgres** | Volume pequeno (50 pacientes), sem dependência de servidor, perfeito pro caso acadêmico | `assistant/tools/patient_records.py` |
| **LangChain LCEL com RunnableLambda** | LCEL puro fica ilegível com 3 fontes de contexto; `RunnableLambda` mantém composição sem boilerplate | `assistant/chain.py:build_medical_chain` |

---

## Próximas fases

- **Fase 5**: LangGraph substitui a `RunnableLambda` da chain por um grafo
  de estado explícito; adiciona geração de alertas pra equipe quando
  detectar emergência.
- **Fase 6**: guardrails programáticos (filtros de entrada/saída,
  validação de claims, log estruturado de auditoria).
- **Fase 7**: API FastAPI + UI Streamlit, expondo a chain via HTTP.
