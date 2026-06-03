"""CSS customizado da UI Streamlit (Fase 7).

Paleta sóbria — azul/cinza, contexto médico. Modo apresentação aumenta
fontes e esconde elementos técnicos pro screencast do vídeo.

Os avisos éticos (banner topo + footer toda resposta) NÃO somem nunca,
mesmo em modo apresentação. Regra explícita do prompt da fase.
"""

from __future__ import annotations

# Paleta
COLOR_PRIMARY = "#1f3a5f"      # azul médico
COLOR_BG = "#f5f7fa"           # cinza claro
COLOR_DANGER = "#d32f2f"       # vermelho — guardrails block
COLOR_WARNING = "#f9a825"      # amarelo — urgência alta / alerta
COLOR_SUCCESS = "#388e3c"      # verde — resposta com fontes
COLOR_MUTED = "#757575"        # cinza — sem fontes


def base_css() -> str:
    """CSS base — paleta, banners, badges. Sempre carregado."""
    return f"""
    <style>
    /* ── Tipografia geral ────────────────────────────────────────── */
    .main .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }}

    /* ── Banner ético no topo ───────────────────────────────────── */
    .ethics-banner {{
        background: #fff4e1;
        border-left: 4px solid {COLOR_WARNING};
        padding: 0.7rem 1rem;
        margin-bottom: 1.2rem;
        border-radius: 4px;
        font-size: 0.9rem;
        color: #5a4a1a;
    }}

    /* ── Footer ético em cada resposta ──────────────────────────── */
    .ethics-footer {{
        margin-top: 0.8rem;
        padding: 0.5rem 0.8rem;
        background: #fafafa;
        border-left: 3px solid {COLOR_MUTED};
        font-size: 0.82rem;
        color: #555;
        border-radius: 3px;
    }}

    /* ── Badges de status / severidade ──────────────────────────── */
    .badge {{
        display: inline-block;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.3rem;
        color: #fff;
    }}
    .badge-danger  {{ background: {COLOR_DANGER}; }}
    .badge-warning {{ background: {COLOR_WARNING}; color: #3a2a00; }}
    .badge-success {{ background: {COLOR_SUCCESS}; }}
    .badge-muted   {{ background: {COLOR_MUTED}; }}
    .badge-primary {{ background: {COLOR_PRIMARY}; }}

    /* ── Box de resposta destacada ──────────────────────────────── */
    .response-card {{
        background: #fff;
        border: 1px solid #e0e0e0;
        border-left: 4px solid {COLOR_PRIMARY};
        padding: 1rem 1.2rem;
        border-radius: 4px;
        margin-top: 0.8rem;
    }}
    .response-card.danger  {{ border-left-color: {COLOR_DANGER}; }}
    .response-card.warning {{ border-left-color: {COLOR_WARNING}; }}
    .response-card.success {{ border-left-color: {COLOR_SUCCESS}; }}
    .response-card.muted   {{ border-left-color: {COLOR_MUTED}; }}

    /* ── Status da API (sidebar) ────────────────────────────────── */
    .api-status-ok  {{ color: {COLOR_SUCCESS}; font-weight: 600; }}
    .api-status-err {{ color: {COLOR_DANGER}; font-weight: 600; }}

    /* ── Mini dados de paciente ────────────────────────────────── */
    .patient-card {{
        background: #f0f4f8;
        padding: 0.6rem 0.9rem;
        border-radius: 4px;
        font-size: 0.88rem;
        margin: 0.4rem 0;
    }}
    .patient-card b {{ color: {COLOR_PRIMARY}; }}
    </style>
    """


def presentation_css() -> str:
    """CSS aplicado SOMENTE em modo apresentação.

    Aumenta fontes, oculta elementos técnicos (request_ids longos, traces).
    Banner ético e footer continuam visíveis — regra da fase.
    """
    return """
    <style>
    .main .block-container {
        font-size: 1.08rem;
    }
    .stMarkdown p, .stMarkdown li {
        font-size: 1.08rem;
        line-height: 1.55;
    }
    .response-card {
        font-size: 1.1rem;
    }
    /* esconde IDs longos e traces em modo apresentação */
    .tech-detail {
        display: none !important;
    }
    </style>
    """
