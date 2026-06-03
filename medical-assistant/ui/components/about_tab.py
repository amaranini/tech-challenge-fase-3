"""Tab Sobre — descrição do sistema + stack + aviso ético reforçado."""

from __future__ import annotations

import streamlit as st


def render_about_tab() -> None:
    st.subheader("🩺 Medical Assistant — Tech Challenge Fase 3")
    st.markdown(
        """
        Sistema de **demonstração** de um assistente clínico que combina:

        - **LLM fine-tuned com LoRA** (Qwen2.5-1.5B-Instruct + adapter próprio)
        - **RAG** sobre protocolos clínicos institucionais (Chroma)
        - **Tool de prontuário** sintético em SQLite
        - **Orquestração via LangGraph** (10 nós com guardrails de entrada e saída)
        - **Auditoria** persistida em SQLite com explainability por consulta

        **Stack:**

        | Camada | Tecnologia |
        |---|---|
        | LLM | MLX-LM (Apple Silicon) ou Ollama |
        | RAG | ChromaDB + sentence-transformers (multilingual MiniLM) |
        | Orquestração | LangGraph (StateGraph) |
        | API | FastAPI + Uvicorn |
        | UI | Streamlit |
        | Persistência | SQLite (pacientes + audit + Chroma) |
        | Fine-tuning | PEFT/LoRA, treinado em Google Colab (T4) |
        """
    )

    st.divider()

    st.markdown("### ⚠️ Avisos importantes")
    st.error(
        "🩺 **Sistema de demonstração — dados sintéticos.** "
        "Não usar em decisões clínicas reais. "
        "Pacientes, exames e protocolos foram gerados sinteticamente para fins "
        "acadêmicos."
    )
    st.warning(
        "⚖️ **Apoio à decisão, nunca substituto.** "
        "Toda conduta clínica requer validação de profissional habilitado. "
        "O sistema possui guardrails que bloqueiam prescrições diretas, "
        "diagnósticos definitivos e decisões clínicas críticas — mas isso é "
        "uma rede de segurança, não uma garantia de correção da resposta."
    )

    st.divider()

    st.markdown("### 🔍 Como funciona uma consulta")
    st.markdown(
        """
        Cada pergunta passa por **10 nós** num grafo de estado:

        1. **Input guardrail** — detecta tentativas de bypass (jailbreak)
        2. **Classificação** — clínica / administrativa / fora de escopo
        3. **Triagem de urgência** — alta / média / baixa (via LLM)
        4. **Busca de paciente** — se o ID estiver presente
        5. **Exames pendentes** — consulta tabela auxiliar
        6. **RAG** — busca os top-3 chunks de protocolo (threshold 0.55)
        7. **Geração** — resposta enriquecida com contexto + histórico
        8. **Guardrails de saída** — 4 categorias, com reescrita se acionarem block
        9. **Emissão de alerta** — se urgência alta, grava em `alerts.jsonl`
        10. **Finalização** — agrega resposta + fontes + disclaimer

        Cada etapa é persistida no audit DB com `request_id` único, e a ficha
        de raciocínio (explainability) decompõe pra o médico **o que foi
        consultado, o que foi acionado, e quanto demorou cada nó**.
        """
    )

    st.divider()

    st.caption(
        "Autoria: Ana Luzia Maranini — Pós-graduação em IA para Devs (FIAP). "
        "Código no GitHub do projeto privado."
    )
