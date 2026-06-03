# Apêndice A — Estrutura do repositório

Snapshot gerado com `tree -L 2 -I '__pycache__|*.pyc|.venv|raw|node_modules|.git'`
a partir da raiz `medical-assistant/`.

```
.
├── DECISIONS.md
├── README.md
├── api
│   ├── README.md
│   ├── __init__.py
│   ├── dependencies.py
│   ├── schemas.py
│   ├── server.py
│   └── test_endpoints.py
├── assistant
│   ├── README.md
│   ├── __init__.py
│   ├── audit
│   ├── chain.py
│   ├── config.py
│   ├── data
│   ├── demo_chat.py
│   ├── demo_graph.py
│   ├── explainability.py
│   ├── graph.py
│   ├── graph_nodes.py
│   ├── graph_prompts.py
│   ├── graph_state.py
│   ├── guardrails
│   ├── intent_classifier.py
│   ├── llm.py
│   ├── prompts.py
│   ├── rag
│   ├── router.py
│   ├── test_chain.py
│   ├── test_classifier_prompts.py
│   ├── test_explainability.py
│   ├── test_graph_integration.py
│   ├── test_graph_nodes.py
│   ├── test_llm.py
│   ├── test_rag.py
│   ├── test_router.py
│   └── tools
├── data
│   ├── README.md
│   ├── anonymization.py
│   ├── generate_synthetic.py
│   ├── inspect_dataset.py
│   ├── prepare_dataset.py
│   ├── processed
│   ├── synthetic
│   └── test_anonymization.py
├── docs
│   ├── arquitetura_fase4.md
│   ├── arquitetura_fase5.md
│   ├── arquitetura_fase6.md
│   ├── langgraph_flow.md
│   ├── langgraph_flow.png
│   ├── langgraph_flow_auto.md
│   └── relatorio
├── evaluation
│   ├── calibrate_rag_threshold.py
│   ├── comparison.md
│   ├── comparison_phase3.md
│   ├── comparison_phase4.md
│   ├── comparison_phase4_th050.md
│   ├── eval_graph.py
│   ├── eval_guardrails.py
│   ├── eval_rag.py
│   ├── eval_system_prompt.py
│   ├── graph_eval_results.md
│   ├── graph_traces
│   ├── guardrails_eval_results.md
│   ├── metrics.json
│   └── rag_threshold_calibration_results.md
├── finetuning
│   ├── README.md
│   ├── chat.py
│   ├── configs
│   ├── data
│   ├── evaluate.py
│   ├── output
│   ├── plot_training.py
│   ├── prepare_mlx_dataset.py
│   └── train.py
├── logging_
│   ├── alerts.jsonl
│   ├── audit.db
│   ├── graph_traces.jsonl
│   └── logs
├── notebooks
├── pyproject.toml
├── scripts
│   └── run_all.sh
├── ui
│   ├── README.md
│   ├── __init__.py
│   ├── app.py
│   ├── client.py
│   ├── components
│   └── styles.py
└── uv.lock
```

**26 diretórios, 72 arquivos** no nível `-L 2`.

## Mapeamento pacote → fase

| Diretório | Fase principal | Conteúdo |
|---|---|---|
| `data/` | 1 | Geração e anonimização do dataset sintético |
| `finetuning/` | 2 | Treino LoRA via mlx-lm + avaliação |
| `assistant/` | 3-6 | LLM wrapper, RAG, grafo, guardrails, audit, explainability |
| `assistant/rag/` | 4 | Build index + retriever Chroma |
| `assistant/tools/` | 4 | Patient lookup (SQLite) |
| `assistant/audit/` | 6 | Writer, reader, CLI do audit DB |
| `assistant/guardrails/` | 6 | 5 categorias + registry + reescrita |
| `api/` | 7 | FastAPI server, 6 endpoints |
| `ui/` | 7 | Streamlit (3 tabs) |
| `scripts/` | 7 | `run_all.sh` (sobe API + UI) |
| `evaluation/` | transversal | Scripts e resultados de avaliação por fase |
| `docs/` | transversal | Arquitetura por fase + diagramas + este relatório |
| `logging_/` | transversal | Audit DB + traces + alertas (gitignored) |
