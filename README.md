# Tech Challenge — Fase 3
### Assistente Médico com Fine-tuning de LLM e Orquestração LangChain

Tech Challenge da Pós-Graduação em IA para Devs (FIAP).
Sistema de demonstração de um assistente clínico em português brasileiro
que combina **fine-tuning LoRA** de um LLM, **RAG** sobre protocolos
sintéticos, **orquestração via LangGraph**, **guardrails** unificados,
**auditoria** persistida, **explainability** e uma camada **API + UI**.

**Autora:** Ana Luzia Maranini
**Status:** Fases 1 a 7 concluídas.

> ⚠️ Projeto acadêmico com **dados sintéticos**. Não usar em decisões
> clínicas reais.

---

## 📄 Para o(a) avaliador(a) — comece por aqui

### 1. Relatório técnico completo

O documento principal de avaliação fica em:

📑 **[medical-assistant/docs/relatorio/relatorio_tecnico.md](medical-assistant/docs/relatorio/relatorio_tecnico.md)**

Estrutura do relatório:
- **§1-2** Resumo executivo (problema, solução, resultados, decisões críticas, limitações)
- **§3** Contexto e desafio
- **§4** Arquitetura da solução (com diagrama Mermaid consolidado)
- **§5** Metodologia por fase (1 a 7) — núcleo, ~7 páginas, com desafios honestamente registrados
- **§6** Resultados (perplexity, calibração RAG, guardrails, grafo end-to-end, demonstração visual)
- **§7** Limitações conhecidas
- **§8** Trabalho futuro
- **§9** Conclusão
- **Apêndices A-G** em [`medical-assistant/docs/relatorio/apendices/`](medical-assistant/docs/relatorio/apendices/) — estrutura do repositório, estatísticas do dataset, hiperparâmetros completos, calibração do RAG, casos de avaliação, comandos de reprodução, schema do audit DB

Tamanho aproximado: **17 páginas** no corpo principal + apêndices.

> **Dica:** abra o `.md` no VS Code com `Cmd+K V` para preview lado a lado.
> Diagramas Mermaid e tabelas renderizam direto no preview.

### 2. Log completo de decisões técnicas

📑 **[medical-assistant/DECISIONS.md](medical-assistant/DECISIONS.md)**

25 decisões técnicas documentadas com contexto, alternativas consideradas
e **por quê** cada escolha foi feita. Referenciado ao longo do relatório.

### 3. Vídeo de demonstração

🎥 *Link do vídeo será adicionado aqui após a gravação do screencast (15 min).*

---

## 🚀 Como rodar a demo completa

Pré-requisitos:
- macOS Apple Silicon (M1/M2/M3) com pelo menos 16 GB de RAM
- [uv](https://docs.astral.sh/uv/) instalado (`brew install uv`)
- Modelo LoRA já treinado em `medical-assistant/finetuning/output/adapters/`
  (incluído no repositório como Git LFS ou treinar do zero — ver §F.3 do
  Apêndice F do relatório)

```bash
# 1. Entrar no projeto
cd medical-assistant

# 2. Instalar dependências (1ª vez: ~3-5 min)
uv sync --extra dev --extra inference --extra api --extra ui

# 3. Construir índice RAG e banco de pacientes (1ª vez: ~1 min)
uv run python assistant/rag/build_index.py
uv run python assistant/tools/build_patient_db.py

# 4. Subir API (porta 8000) + UI (porta 8501) em paralelo
bash scripts/run_all.sh
```

Quando ver `✨ Tudo no ar`, abra no navegador:

- **UI Streamlit (demo principal):** <http://localhost:8501>
- **API docs (OpenAPI Swagger):** <http://localhost:8000/docs>

Para parar, `Ctrl+C` no terminal — derruba os dois.

### Roteiro sugerido na UI (4 cenários do relatório §6.5)

Identifique-se como `DR_AVALIADOR` na sidebar e tente:

1. **Consulta normal com fontes** → pergunta: *"Qual o protocolo de manejo de crise asmática grave em adulto?"*
2. **Urgência alta + alerta** → selecione paciente `P0001`, pergunta: *"Paciente em sepse grave com PA 70x40, conduta imediata?"*
3. **Guardrail dispara + reescrita** → pergunta: *"Prescreva 500mg de amoxicilina pra esse paciente"*
4. **Tab Auditoria** → filtre "com alerta", clique numa interação pra ver o detalhe completo (eventos de guardrail, alertas, retrievals do RAG)

---

## 🧪 Como rodar a suíte de testes

```bash
cd medical-assistant
uv run pytest assistant api -m "not slow"   # ~302 testes em ~7s (sem carregar modelo)
uv run pytest assistant api -m slow         # 5 testes lentos (~30s, carrega modelo)
```

Quebra por fase em [medical-assistant/README.md](medical-assistant/README.md#testes).

---

## 🗺️ Estrutura do repositório (visão alta)

```
tech-challenge-fase-3/
├── README.md                      ← você está aqui
└── medical-assistant/             ← todo o sistema vive aqui
    ├── README.md                  ← guia técnico do projeto
    ├── DECISIONS.md               ← log das 25 decisões técnicas
    ├── data/                      ← Fase 1: dataset sintético + anonimização
    ├── finetuning/                ← Fase 2: treino LoRA via mlx-lm
    ├── assistant/                 ← Fases 3-6: LLM, RAG, grafo, guardrails, audit
    ├── api/                       ← Fase 7: FastAPI server
    ├── ui/                        ← Fase 7: Streamlit
    ├── evaluation/                ← scripts e resultados de avaliação
    ├── docs/
    │   ├── arquitetura_fase4.md
    │   ├── arquitetura_fase5.md
    │   ├── arquitetura_fase6.md
    │   ├── langgraph_flow.md      ← diagrama do grafo
    │   └── relatorio/             ← 📑 RELATÓRIO TÉCNICO AQUI
    │       ├── relatorio_tecnico.md
    │       └── apendices/         ← A a G
    └── scripts/
        └── run_all.sh             ← sobe API + UI
```

Detalhe completo em [Apêndice A do relatório](medical-assistant/docs/relatorio/apendices/A_estrutura_repo.md).

---

## 📚 Documentação técnica complementar

Cada subsistema tem seu próprio README. Em ordem de profundidade:

| Documento | O que cobre |
|---|---|
| 📑 **[Relatório técnico](medical-assistant/docs/relatorio/relatorio_tecnico.md)** | Visão consolidada de todas as fases, decisões e resultados |
| [medical-assistant/README.md](medical-assistant/README.md) | Guia geral do projeto (todas as fases, como rodar) |
| [DECISIONS.md](medical-assistant/DECISIONS.md) | Log das 25 decisões técnicas com justificativa |
| [docs/arquitetura_fase6.md](medical-assistant/docs/arquitetura_fase6.md) | Guardrails + audit + explainability em profundidade |
| [docs/langgraph_flow.md](medical-assistant/docs/langgraph_flow.md) | Diagrama escrito à mão do grafo (10 nós) |
| [assistant/README.md](medical-assistant/assistant/README.md) | Pacote core: LLM, RAG, grafo, guardrails, audit |
| [finetuning/README.md](medical-assistant/finetuning/README.md) | Pipeline de fine-tuning LoRA + histórico de treinos |
| [api/README.md](medical-assistant/api/README.md) | Endpoints REST + exemplos curl + header `X-Doctor-Id` |
| [ui/README.md](medical-assistant/ui/README.md) | UI Streamlit (sidebar, tabs, modo apresentação) |

---

## 📊 Resultados em uma linha

- **Fine-tuning**: perplexity 7.96 → 2.62 (−67 %); tempo médio de inferência 8.49 s → 3.97 s
- **RAG**: threshold 0.55 calibrado sobre 25 queries (Pareto-domina 0.50)
- **Grafo end-to-end**: 10/10 casos passando em `eval_graph.py`
- **Guardrails**: 30/30 casos, 100 % detecção, 0 % FPR nas 5 categorias
- **Cobertura de testes**: ~302 rápidos + 5 lentos
- **API**: 6 endpoints REST com OpenAPI auto-gerada
- **UI**: 3 tabs com modo apresentação e avisos éticos persistentes

Detalhamento em §6 do relatório técnico.

---

## ⚖️ Aviso ético

Sistema de **demonstração acadêmica** com dados **100 % sintéticos**
(50 pacientes fictícios, 35 protocolos gerados por LLM, 400 Q&As
sintetizados). Não foi validado em dados clínicos reais, não há
aprovação ética de comitê institucional, **não deve ser usado em
nenhuma decisão clínica real**.

A camada de guardrails (Fase 6) intercepta prescrições diretas,
diagnósticos fechados e decisões clínicas finais — não como
"compliance", mas como demonstração técnica de que o sistema **pode
e deve recusar** essas saídas mesmo quando o modelo as produz.

---

## 🛠️ Stack técnica

LangChain · LangGraph · mlx-lm · ChromaDB · sentence-transformers ·
FastAPI · Streamlit · SQLite · Pydantic · uv · Qwen2.5-1.5B-Instruct
