# Apêndice F — Comandos de reprodução

Sequência completa para reproduzir o projeto do zero. Cada bloco
assume que o anterior foi executado com sucesso.

## F.1 — Setup inicial (uma vez)

```bash
# Clonar e entrar
git clone <repo> && cd medical-assistant

# Instalar dependências (todas as extras pra demo)
uv sync --extra data --extra dev --extra inference --extra api --extra ui

# Configurar .env (só se for regenerar dataset — OPENAI_API_KEY)
cp .env.example .env
# editar .env e colar a chave
```

## F.2 — Fase 1: Geração e curadoria do dataset

```bash
# Modelo de NER em PT-BR
uv run python -m spacy download pt_core_news_lg

# Testes da pipeline de anonimização
uv run pytest data/test_anonymization.py -v

# Geração sintética (chamadas OpenAI — leva ~10 min)
uv run python data/generate_synthetic.py

# Splits de train/val/test
uv run python data/prepare_dataset.py
```

Saídas:
- `data/synthetic/{patients.csv, protocols/, qa_pairs.jsonl, refusals.jsonl}`
- `data/processed/{train, val, test}.jsonl` (508 exemplos)
- `data/processed/dataset_report.md`

## F.3 — Fase 2: Fine-tuning

```bash
# Sanity check do MLX (esperar 'device: Device(gpu, 0)')
uv run python -c "import mlx.core as mx; print('device:', mx.default_device())"

# Prepara dataset no formato mlx-lm
uv run python finetuning/prepare_mlx_dataset.py

# Smoke test (10 iters, ~2-3 min) — OBRIGATÓRIO antes do treino real
uv run python finetuning/train.py --smoke-test

# Treino real (~11 min no M1 16 GB)
uv run python finetuning/train.py

# Gráficos
uv run python finetuning/plot_training.py

# Avaliação automatizada (perplexity + 10 prompts qualitativos)
uv run python finetuning/evaluate.py
```

Saídas:
- `finetuning/output/adapters/` (adapter LoRA final)
- `finetuning/output/{loss_curve.png, lr_schedule.png, training_log.json}`
- `evaluation/metrics.json`
- `evaluation/comparison.md`

## F.4 — Fase 4: Índice RAG e banco de pacientes

```bash
# Indexa os 35 protocolos no Chroma (~30-90 s; primeira vez baixa MiniLM)
uv run python assistant/rag/build_index.py

# Popula assistant/data/patients.db com 50 pacientes
uv run python assistant/tools/build_patient_db.py

# Smoke tests
uv run python -m assistant.rag.retriever "Como manejar sepse?"
uv run python -m assistant.tools.patient_records P0001

# Calibração de threshold (gera Apêndice D)
uv run python evaluation/calibrate_rag_threshold.py

# Avaliação RAG (15 casos)
uv run python evaluation/eval_rag.py
```

Saídas:
- `assistant/data/chroma_db/` (índice persistido)
- `assistant/data/patients.db`
- `evaluation/rag_threshold_calibration_results.md`
- `evaluation/comparison_phase4.md`

## F.5 — Fase 5: Grafo

```bash
# Compila o grafo + exporta diagrama + smoke test
uv run python assistant/graph.py

# Demo interativo (REPL com /trace, /why, /alerts)
uv run python assistant/demo_graph.py

# Avaliação end-to-end (10 casos)
uv run python evaluation/eval_graph.py
```

Saídas:
- `docs/langgraph_flow_auto.md` + `langgraph_flow.png`
- `evaluation/graph_eval_results.md`
- `evaluation/graph_traces/case_NN.json`

## F.6 — Fase 6: Guardrails + audit + explainability

```bash
# Smoke test dos guardrails (sem LLM)
uv run python -m assistant.guardrails "Prescreva 500mg de amoxicilina"

# Avaliação dos 5 guardrails (30 casos)
uv run python evaluation/eval_guardrails.py

# CLI do audit DB (depois de algumas execuções do grafo)
uv run python -m assistant.audit list --last 10
uv run python -m assistant.audit stats
```

Saídas:
- `evaluation/guardrails_eval_results.md`
- `logging_/audit.db` (4 tabelas + WAL + schema v2)

## F.7 — Fase 7: API + UI (demo completa)

```bash
# Sobe API (porta 8000) e UI (porta 8501) em paralelo — Ctrl+C derruba os dois
bash scripts/run_all.sh
```

Abrir no navegador:
- UI: <http://localhost:8501>
- API docs: <http://localhost:8000/docs>

Para rodar separadamente:

```bash
# Terminal 1
uv run uvicorn api.server:app --reload --port 8000

# Terminal 2
uv run streamlit run ui/app.py
```

## F.8 — Suite de testes completa

```bash
# Rápidos (~7 s, sem carregar modelo)
uv run pytest assistant api -m "not slow" -v

# Lentos (~30 s, carrega modelo)
uv run pytest assistant api -m slow -v
```

Esperado: 302 testes rápidos + 5 lentos passando.

## F.9 — Geração do PDF deste relatório

```bash
# Pré-requisito (uma vez): pandoc + LaTeX
brew install pandoc basictex
sudo tlmgr update --self
sudo tlmgr install collection-fontsrecommended collection-latexrecommended

# Conversão
cd docs/relatorio
pandoc relatorio_tecnico.md -o relatorio_tecnico.pdf \
  --pdf-engine=xelatex \
  --toc --toc-depth=2 \
  --number-sections \
  -V geometry:margin=2.5cm \
  -V mainfont="Helvetica" \
  -V monofont="Menlo" \
  -V colorlinks=true
```

Alternativa sem instalar LaTeX: **VS Code + extensão Markdown PDF**.
