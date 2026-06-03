# `api/` — FastAPI HTTP exposing the medical graph (Fase 7)

API REST que expõe o grafo LangGraph médico. Carrega o modelo **1x no
startup** (não a cada request) e persiste cada consulta no audit DB.

A UI Streamlit (em [`../ui`](../ui)) consome esta API via HTTP — nada de
importar o grafo direto. Isso simula um deployment real e permite trocar a
UI sem mexer no servidor.

---

## Como rodar

```bash
# Instalação (se ainda não fez)
uv sync --extra api --extra inference --extra dev

# Sobe o servidor (recarrega em mudanças de código)
uv run uvicorn api.server:app --reload --port 8000
```

O primeiro start demora ~30-60s carregando o modelo MLX + retriever Chroma.
O servidor imprime o tempo no log. Em seguida:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Docs interativas**: <http://localhost:8000/docs> (Swagger UI gerado pelo FastAPI).

---

## Endpoints

| Método | Path                       | Descrição                                              |
|--------|----------------------------|--------------------------------------------------------|
| GET    | `/health`                  | Diagnóstico (model_loaded, db_accessible, version)     |
| GET    | `/patients`                | Lista pacientes (id, nome, idade, sexo)                |
| GET    | `/patients/{patient_id}`   | Detalhe + exames pendentes                              |
| POST   | `/consult`                 | Roda o grafo + persiste audit                           |
| GET    | `/audit`                   | Lista paginada filtrável                                |
| GET    | `/audit/{request_id}`      | Detalhe (events + alerts + retrievals)                  |

### Header obrigatório em `/consult`

`X-Doctor-Id: <string>` — identificador do médico. É gravado em
`interactions.doctor_id` no audit DB. **Autenticação simulada** (sem
validação real) — demonstra que o sistema rastreia QUEM consultou.

---

## Exemplos com `curl`

```bash
# Health
curl http://localhost:8000/health | jq

# Listar pacientes
curl http://localhost:8000/patients | jq

# Detalhe de paciente
curl http://localhost:8000/patients/P0001 | jq

# Consulta clínica
curl -X POST http://localhost:8000/consult \
  -H "X-Doctor-Id: DR_SILVA" \
  -H "Content-Type: application/json" \
  -d '{"question": "Qual o protocolo para crise asmática?", "patient_id": "P0001"}' | jq

# Listar últimas 10 consultas
curl 'http://localhost:8000/audit?limit=10' | jq

# Filtrar consultas com alerta de urgência alta
curl 'http://localhost:8000/audit?has_alerts=true' | jq

# Detalhe completo de uma consulta (use o request_id retornado por /consult)
curl http://localhost:8000/audit/<request_id> | jq
```

---

## Arquitetura

```
api/
├── server.py         # FastAPI app, lifespan, endpoints
├── schemas.py        # Modelos Pydantic (request/response)
├── dependencies.py   # Injeções: X-Doctor-Id, AuditReader, GraphRunner
├── test_endpoints.py # Testes com httpx.TestClient (grafo mockado)
└── README.md         # você está aqui
```

### Fluxo de uma consulta

```
POST /consult
  ↓
require_doctor_id() → 400 se header ausente
  ↓
ConsultRequest validado (Pydantic) → 422 se patient_id mal-formado
  ↓
run_medical_graph(question, patient_id, doctor_id)
  ↓ (singleton — modelo já carregado)
LangGraph executa 10 nós
  ↓
AuditWriter grava em audit.db (defensivo — exceção não propaga)
  ↓
build_explanation(state) → ficha de raciocínio
  ↓
ConsultResponse devolvido (final_response, explanation, latency_ms, …)
```

---

## Testes

```bash
# Rápidos (~2s) — grafo mockado via dependency_overrides
uv run pytest api/ -v

# Lentos (sobem o servidor de verdade — descomentar @slow primeiro)
uv run pytest api/ -v -m slow
```

Os testes usam `app.state.skip_warmup = True` pra pular o carregamento do
modelo no lifespan, e `app.dependency_overrides[run_graph_callable]` pra
substituir o runner por uma função fake. Zero coupling com o modelo real
nos testes rápidos.

---

## Notas

- **Modelo**: carrega 1x no startup. Singleton em `assistant.graph._GRAPH_SINGLETON`.
- **CORS**: liberado para `http://localhost:8501` (UI Streamlit).
- **Audit DB**: gravação defensiva. Se falhar, log no stderr — a resposta segue.
- **Schema do audit DB**: migra automaticamente para v2 no startup (coluna `doctor_id`).
- **Erro genérico**: capturado e devolvido como `500` com mensagem; nada de stacktrace pro cliente.
