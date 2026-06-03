"""Tab Consulta — formulário de pergunta + resposta + ficha de raciocínio.

Fluxo:
1. Médico opcionalmente seleciona um paciente (carrega dados do /patients/{id})
2. Digita uma pergunta clínica
3. Clica "Consultar" → POST /consult com X-Doctor-Id
4. Resposta é renderizada com:
   - badges de status (urgência, has_alert, was_rewritten, fontes)
   - corpo da resposta (markdown)
   - footer ético (sempre visível)
   - expansíveis: fontes, ficha de raciocínio, trace

A cor do card de resposta segue o estado mais relevante:
- danger  (vermelho) se foi reescrita por guardrail
- warning (amarelo)  se houve alerta de urgência alta
- success (verde)    se tem fontes
- muted   (cinza)    sem fontes
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from client import APIClient, is_error


# ────────────────────────────────────────────────────────────────────────
# Helpers visuais
# ────────────────────────────────────────────────────────────────────────

def _card_class(payload: dict) -> str:
    """Decide cor do card baseado no estado da resposta."""
    if payload.get("was_rewritten"):
        return "danger"
    if payload.get("has_alert") or payload.get("urgency") == "alta":
        return "warning"
    explanation = payload.get("explanation") or {}
    if explanation.get("sources"):
        return "success"
    return "muted"


def _render_badges(payload: dict) -> None:
    """Badges de status no topo da resposta."""
    chips: list[str] = []
    intent = payload.get("intent")
    urgency = payload.get("urgency")
    if intent:
        chips.append(f'<span class="badge badge-primary">intent: {intent}</span>')
    if urgency == "alta":
        chips.append('<span class="badge badge-warning">⚠ urgência alta</span>')
    elif urgency:
        chips.append(f'<span class="badge badge-muted">urgência: {urgency}</span>')
    if payload.get("has_alert"):
        chips.append('<span class="badge badge-warning">🚨 alerta emitido</span>')
    if payload.get("was_rewritten"):
        chips.append('<span class="badge badge-danger">✏️ reescrita</span>')
    explanation = payload.get("explanation") or {}
    if explanation.get("sources"):
        chips.append(
            f'<span class="badge badge-success">📚 {len(explanation["sources"])} fonte(s)</span>'
        )
    if chips:
        st.markdown(" ".join(chips), unsafe_allow_html=True)


def _render_patient_card(patient: dict) -> None:
    pe = patient.get("pending_exams") or []
    pending_summary = (
        f"{len(pe)} exame(s) pendente(s)" if pe else "sem exames pendentes"
    )
    html = (
        f'<div class="patient-card">'
        f'<b>{patient.get("nome", "?")}</b> · {patient.get("idade", "?")} anos · '
        f'sexo {patient.get("sexo", "?")} <br/>'
        f'<b>Alergias:</b> {patient.get("alergias") or "—"} · '
        f'<b>Medicações:</b> {patient.get("medicacoes_atuais") or "—"}<br/>'
        f'<b>Histórico:</b> {patient.get("historico_resumido") or "—"}<br/>'
        f'📋 {pending_summary}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_sources(explanation: dict) -> None:
    sources = explanation.get("sources") or []
    if not sources:
        reason = explanation.get("no_sources_reason") or "—"
        st.info(f"Sem fontes RAG. Motivo: {reason}")
        return
    for i, src in enumerate(sources, 1):
        st.markdown(
            f"**{i}.** `{src.get('file', '?')}` → _{src.get('section', '?')}_  "
            f"(score: {src.get('score', 0):.2f})"
        )


def _render_explanation(explanation: dict) -> None:
    """Ficha de raciocínio resumida — versão UI da format_explanation."""
    cls = explanation.get("classification") or {}
    st.markdown(
        f"**Classificação:** intent=`{cls.get('intent')}` · "
        f"urgency=`{cls.get('urgency')}` · "
        f"bypass=`{cls.get('bypass_detected')}`"
    )

    patient = explanation.get("patient_used")
    if patient:
        st.markdown(
            f"**Paciente:** {patient.get('id')} — campos consultados: "
            f"{', '.join(patient.get('fields_consulted', [])) or '—'}"
        )
    else:
        st.markdown("**Paciente:** — (consulta sem paciente)")

    exams = explanation.get("exams_consulted")
    if exams:
        st.markdown(f"**Exames pendentes consultados:** {len(exams)}")
        for e in exams[:3]:
            st.markdown(
                f"- {e.get('tipo_exame')} ({e.get('prioridade')}) — "
                f"solicitado em {e.get('data_solicitacao')}"
            )

    guards = explanation.get("guardrails_triggered") or []
    if guards:
        st.markdown("**Guardrails acionados:**")
        for g in guards:
            level_emoji = "🛑" if g.get("level") == "block" else "⚠️"
            action = g.get("action_taken") or "—"
            st.markdown(
                f"- {level_emoji} `{g.get('name')}` "
                f"({g.get('applies_to')}, {g.get('level')}) → ação: {action}"
            )
    else:
        st.markdown("**Guardrails acionados:** nenhum")

    model_info = explanation.get("model_info") or {}
    st.markdown(
        f"**Modelo:** `{model_info.get('base', '?')}` + adapter "
        f"`{model_info.get('adapter', '?')}`"
    )

    total = explanation.get("total_latency_s")
    if total is not None:
        st.markdown(f"**Latência total do grafo:** {total:.2f}s")


def _render_trace(explanation: dict) -> None:
    """Trace por nó — escondido em modo apresentação via classe CSS."""
    breakdown = explanation.get("latency_breakdown_s") or {}
    if not breakdown:
        st.caption("Sem trace disponível.")
        return
    st.markdown('<div class="tech-detail">', unsafe_allow_html=True)
    for node, latency in breakdown.items():
        bar = "█" * max(1, int(latency * 20))
        st.markdown(f"`{node:<24s}` {latency:>6.3f}s {bar}")
    st.markdown('</div>', unsafe_allow_html=True)


def _ethics_footer() -> None:
    st.markdown(
        '<div class="ethics-footer">⚠️ Apoio à decisão clínica. '
        'Toda conduta requer validação médica.</div>',
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────
# Tab principal
# ────────────────────────────────────────────────────────────────────────

def render_consult_tab(
    client: APIClient,
    doctor_id: str,
    patients: list[dict],
) -> None:
    """Tab Consulta — formulário + render da resposta.

    `patients` é a lista já carregada (em app.py) — economiza request a cada
    re-render. Pode estar vazia se a API estiver offline.
    """
    st.subheader("🩺 Nova consulta")

    # ─── Seletor de paciente ─────────────────────────────────────────
    col_a, col_b = st.columns([2, 1])
    with col_a:
        options = ["(sem paciente)"] + [
            f"{p['id']} — {p['nome']} ({p['idade']}a)"
            for p in patients
        ]
        selection = st.selectbox(
            "Paciente",
            options=options,
            index=0,
            help="Opcional. Quando selecionado, dados são incluídos no contexto.",
        )

    selected_pid: str | None = None
    if selection and selection != "(sem paciente)":
        selected_pid = selection.split(" — ")[0]
        with st.spinner(f"Carregando dados de {selected_pid}…"):
            detail = client.get_patient(selected_pid)
        if is_error(detail):
            st.warning(f"Não consegui carregar dados: {detail.get('detail')}")
        else:
            _render_patient_card(detail)

    # ─── Campo da pergunta ────────────────────────────────────────────
    question = st.text_area(
        "Pergunta clínica",
        height=110,
        placeholder="Ex: Qual o protocolo de manejo de crise asmática grave?",
        key="consult_question",
    )

    submit = st.button("🔎 Consultar", type="primary", use_container_width=False)

    # ─── Submissão ────────────────────────────────────────────────────
    if submit:
        if not question.strip():
            st.error("Digite uma pergunta antes de consultar.")
            return
        if not doctor_id.strip():
            st.error("Identifique-se na sidebar (campo 'Médico') antes de consultar.")
            return

        with st.spinner("Rodando o grafo clínico…"):
            payload = client.consult(question.strip(), selected_pid, doctor_id)

        if is_error(payload):
            st.error(f"Erro na API: {payload.get('detail')}")
            return

        # Adiciona ao histórico da sessão
        history = st.session_state.setdefault("consult_history", [])
        history.append({
            "request_id": payload.get("request_id"),
            "question": question.strip()[:80],
            "urgency": payload.get("urgency"),
            "has_alert": payload.get("has_alert"),
            "was_rewritten": payload.get("was_rewritten"),
        })

        _render_response(payload)


def _render_response(payload: dict[str, Any]) -> None:
    """Renderiza o ConsultResponse retornado pela API."""
    cls = _card_class(payload)
    _render_badges(payload)

    final = payload.get("final_response") or "(resposta vazia)"
    st.markdown(
        f'<div class="response-card {cls}">',
        unsafe_allow_html=True,
    )
    st.markdown(final)
    st.markdown('</div>', unsafe_allow_html=True)
    _ethics_footer()

    # ─── Expansíveis ────────────────────────────────────────────────
    explanation = payload.get("explanation") or {}

    with st.expander(f"📚 Fontes consultadas ({len(explanation.get('sources') or [])})"):
        _render_sources(explanation)

    with st.expander("📋 Ficha de raciocínio (explainability)"):
        _render_explanation(explanation)

    with st.expander("🔬 Trace do grafo (latências por nó)"):
        _render_trace(explanation)

    # request_id (escondido em modo apresentação via classe)
    st.markdown(
        f'<div class="tech-detail" style="font-size:0.78rem;color:#999;">'
        f'request_id: <code>{payload.get("request_id")}</code> · '
        f'latência total: {payload.get("latency_ms")}ms'
        f'</div>',
        unsafe_allow_html=True,
    )
