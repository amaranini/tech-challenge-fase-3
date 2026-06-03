"""UI Streamlit — entry point (Fase 7).

Como rodar:
    cd medical-assistant
    uv run streamlit run ui/app.py

A API precisa estar rodando antes em http://localhost:8000 (ou aponte
para outra URL via env var MEDICAL_API_URL).

Estrutura:
- Sidebar: identificação do médico + status da API + modo apresentação
           + histórico curto da sessão
- Main: 3 tabs (Consulta, Auditoria, Sobre)
- Banner ético no topo — SEMPRE visível, mesmo em modo apresentação
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Garante que o diretório ui/ esteja no sys.path quando o Streamlit roda
# o app a partir do diretório raiz do projeto (`streamlit run ui/app.py`).
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from client import APIClient, is_error  # noqa: E402
from components.about_tab import render_about_tab  # noqa: E402
from components.audit_tab import render_audit_tab  # noqa: E402
from components.consult_tab import render_consult_tab  # noqa: E402
from styles import base_css, presentation_css  # noqa: E402


# ────────────────────────────────────────────────────────────────────────
# Configuração do Streamlit (precisa ser a 1ª chamada)
# ────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Medical Assistant — Demo",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ────────────────────────────────────────────────────────────────────────
# Cliente HTTP (cache de sessão)
# ────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client() -> APIClient:
    """1 instância de APIClient por sessão Streamlit."""
    return APIClient()


client = get_client()


# ────────────────────────────────────────────────────────────────────────
# CSS
# ────────────────────────────────────────────────────────────────────────

st.markdown(base_css(), unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────
# Sidebar — identificação, status, modo apresentação, histórico
# ────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🩺 Identificação")
    doctor_id = st.text_input(
        "Médico",
        value=st.session_state.get("doctor_id", "DR_DEMO"),
        help="Identificador livre — usado no header X-Doctor-Id da API. "
             "Persistido no audit DB.",
    )
    st.session_state["doctor_id"] = doctor_id

    st.divider()

    # ─── Health check ─────────────────────────────────────────────
    st.markdown("### Status da API")
    health = client.health()
    if is_error(health):
        st.markdown(
            f'<span class="api-status-err">● offline</span><br/>'
            f'<small>{health.get("detail")}</small>',
            unsafe_allow_html=True,
        )
    else:
        ok = health.get("status") == "ok" and health.get("model_loaded")
        cls = "api-status-ok" if ok else "api-status-err"
        label = "● online" if ok else "● degradado"
        startup = health.get("startup_seconds")
        startup_str = f"<br/><small>boot: {startup}s</small>" if startup else ""
        st.markdown(
            f'<span class="{cls}">{label}</span>'
            f'<br/><small>v{health.get("version", "?")} · '
            f'model_loaded={health.get("model_loaded")}</small>'
            f'{startup_str}',
            unsafe_allow_html=True,
        )

    st.divider()

    # ─── Modo apresentação ────────────────────────────────────────
    presentation = st.toggle(
        "🎥 Modo apresentação",
        value=False,
        help="Aumenta fontes e esconde detalhes técnicos (IDs, traces). "
             "Avisos éticos permanecem visíveis.",
    )

    st.divider()

    # ─── Histórico da sessão ─────────────────────────────────────
    history = st.session_state.get("consult_history", [])
    if history:
        st.markdown("### Histórico (sessão)")
        for i, h in enumerate(reversed(history[-10:]), 1):
            badges: list[str] = []
            if h.get("has_alert"):
                badges.append("🚨")
            if h.get("was_rewritten"):
                badges.append("✏️")
            if h.get("urgency") == "alta":
                badges.append("⚠️")
            badges_str = " ".join(badges)
            st.caption(f"{badges_str} {h.get('question', '')[:48]}…")


if presentation:
    st.markdown(presentation_css(), unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────
# Banner ético no topo (SEMPRE visível, mesmo em apresentação)
# ────────────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="ethics-banner">'
    '🩺 <b>Sistema de demonstração — dados sintéticos.</b> '
    'Não usar em decisões clínicas reais.'
    '</div>',
    unsafe_allow_html=True,
)


# ────────────────────────────────────────────────────────────────────────
# Pré-carrega lista de pacientes 1x por sessão (pra dropdown)
# ────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_patients() -> list[dict]:
    """Cache de 60s — pacientes não mudam durante a sessão."""
    res = client.list_patients(limit=100)
    if is_error(res):
        return []
    return res  # type: ignore[return-value]


patients = _load_patients()


# ────────────────────────────────────────────────────────────────────────
# Tabs
# ────────────────────────────────────────────────────────────────────────

tab_consult, tab_audit, tab_about = st.tabs(["🔎 Consulta", "📊 Auditoria", "ℹ️ Sobre"])

with tab_consult:
    render_consult_tab(client, doctor_id, patients)

with tab_audit:
    render_audit_tab(client)

with tab_about:
    render_about_tab()
