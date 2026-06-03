"""Tab Auditoria — lista filtrável + detalhe expandido.

Consome:
- GET /audit          (lista filtrável)
- GET /audit/{id}     (detalhe completo)

Filtros são mutuamente exclusivos (a API trata na prioridade).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from client import APIClient, is_error


def _format_row(row: dict) -> dict[str, Any]:
    """Aplica emojis nas flags pra ficar visualmente óbvio na tabela."""
    return {
        "ts": (row.get("ts") or "")[:19],          # corta milissegundos
        "doctor": row.get("doctor_id") or "—",
        "paciente": row.get("patient_id") or "—",
        "intent": row.get("intent") or "—",
        "urgência": row.get("urgency") or "—",
        "guardrail": "🛑" if row.get("has_guardrail") else "",
        "alerta": "🚨" if row.get("has_alert") else "",
        "bypass": "🛡️" if row.get("bypass_detected") else "",
        "ms": row.get("latency_ms") or 0,
        "pergunta": (row.get("question") or "")[:80],
        "request_id": row.get("request_id"),
    }


def _render_detail(detail: dict) -> None:
    """Detalhe completo de uma interação — chamada pelo expander/modal."""
    if is_error(detail):
        st.error(f"Erro ao carregar detalhe: {detail.get('detail')}")
        return

    st.markdown(f"### Interação `{detail.get('request_id')}`")
    st.markdown(
        f"**Timestamp:** {detail.get('ts')}  ·  "
        f"**Médico:** `{detail.get('doctor_id') or '—'}`  ·  "
        f"**Paciente:** `{detail.get('patient_id') or '—'}`"
    )
    st.markdown(
        f"**Intent:** `{detail.get('intent')}`  ·  "
        f"**Urgência:** `{detail.get('urgency')}`  ·  "
        f"**Bypass:** `{detail.get('bypass_detected')}`"
    )

    st.markdown("**Pergunta:**")
    st.code(detail.get("question") or "—", language="text")

    if detail.get("response"):
        st.markdown("**Resposta gravada:**")
        st.markdown(
            f'<div class="response-card">{detail["response"]}</div>',
            unsafe_allow_html=True,
        )

    # ─── Guardrail events ─────────────────────────────────────────
    events = detail.get("guardrail_events") or []
    triggered = [e for e in events if e.get("triggered")]
    st.markdown(f"**Guardrails:** {len(events)} avaliados, {len(triggered)} acionados")
    if triggered:
        df = pd.DataFrame([
            {
                "nome": e.get("guardrail_name"),
                "lado": e.get("applies_to"),
                "nível": e.get("level"),
                "ação": e.get("action_taken") or "—",
                "severidade": f"{(e.get('severity') or 0):.2f}",
                "padrões": ", ".join(e.get("matched_patterns") or [])[:60],
            }
            for e in triggered
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ─── Alerts ───────────────────────────────────────────────────
    alerts = detail.get("alerts") or []
    if alerts:
        st.markdown(f"**Alertas:** {len(alerts)}")
        for a in alerts:
            st.warning(
                f"🚨 Urgência {a.get('urgency')} — {a.get('summary')} "
                f"(paciente: {a.get('patient_id') or '—'})"
            )

    # ─── RAG retrievals ───────────────────────────────────────────
    rag = detail.get("rag_retrievals") or []
    if rag:
        for r in rag:
            top = r.get("top_k_results") or []
            st.markdown(
                f"**RAG:** query=`{r.get('query', '')[:60]}` — "
                f"{len(top)} chunks, had_sources={r.get('had_sources')}"
            )
            for chunk in top[:3]:
                st.markdown(
                    f"- `{chunk.get('source_file')}` → _{chunk.get('section')}_ "
                    f"(score: {chunk.get('score', 0):.2f})"
                )


def render_audit_tab(client: APIClient) -> None:
    st.subheader("📊 Auditoria")
    st.caption(
        "Histórico de consultas persistido em `logging_/audit.db`. "
        "Os filtros consultam o mesmo banco que a CLI `assistant.audit`."
    )

    # ─── Filtros ──────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        limit = st.number_input("Quantos", min_value=5, max_value=200, value=20, step=5)
    with col2:
        flt = st.radio(
            "Filtro",
            ["todos", "com alerta", "com guardrail"],
            horizontal=False,
            label_visibility="visible",
        )
    with col3:
        patient_filter = st.text_input(
            "ID paciente",
            placeholder="P0001",
            help="Sobrepõe outros filtros se preenchido.",
        )
    with col4:
        if st.button("🔄 Atualizar"):
            # Força re-fetch — Streamlit já re-renderiza a cada interação,
            # mas isso deixa explícito.
            pass

    # ─── Fetch ────────────────────────────────────────────────────
    pid = patient_filter.strip() or None
    items = client.list_audit(
        limit=int(limit),
        has_alerts=(flt == "com alerta"),
        has_guardrail=(flt == "com guardrail"),
        patient_id=pid,
    )

    if is_error(items):
        st.error(f"Erro: {items.get('detail')}")
        return
    if not items:
        st.info("Nenhuma interação encontrada com esses filtros.")
        return

    # ─── Tabela ───────────────────────────────────────────────────
    rows = [_format_row(it) for it in items]
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "request_id": st.column_config.TextColumn(width="small"),
            "pergunta": st.column_config.TextColumn(width="large"),
        },
    )

    # ─── Detalhe via select ──────────────────────────────────────
    rid_options = [it["request_id"] for it in items]
    selected = st.selectbox(
        "Ver detalhe de:",
        options=["—"] + rid_options,
        index=0,
    )
    if selected and selected != "—":
        detail = client.get_audit_detail(selected)
        with st.container(border=True):
            _render_detail(detail)
