"""Ficha de raciocínio (explainability) — Fase 6, Bloco 3.

Filosofia: a explicação NÃO é o LLM "explicando" — é o sistema decompondo,
sobre o `state` final do grafo, o que aconteceu. Função pura, sem chamar
LLM, sem latência adicional.

API pública:
- `build_explanation(state) -> dict`  — função pura, dict serializável
- `format_explanation(exp, *, detail=False)` — render rich (Panel)

Por que NÃO pedir ao LLM pra explicar:
- O LLM produziria texto plausível mas não EVIDÊNCIA. Pode inventar fontes
  que não foram consultadas, justificativas que não tiveram.
- Latência: o ponto da fase é decomposição auditável; chamar o LLM aqui
  é estranho.
- O `state` do grafo já é o oráculo da verdade — basta enumerar.
"""

from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from assistant.config import ADAPTER_PATH, MODEL_PATH
from assistant.graph_state import MedicalState


# ────────────────────────────────────────────────────────────────────────
# build_explanation: state → dict serializável
# ────────────────────────────────────────────────────────────────────────

def _patient_fields_consulted(patient_data: dict | None) -> list[str]:
    """Lista os campos do prontuário com valor não-vazio."""
    if not patient_data:
        return []
    fields_of_interest = (
        "nome", "idade", "sexo", "alergias",
        "medicacoes_atuais", "historico_resumido",
    )
    consulted = []
    for f in fields_of_interest:
        v = patient_data.get(f)
        if v not in (None, "", []):
            consulted.append(f)
    return consulted


def _no_sources_reason(state: MedicalState) -> str | None:
    """Inferir motivo de não haver fontes RAG.

    None se rag_has_sources for True OU se o RAG nem rodou (caminho refuse).
    """
    nodes = [t.get("node") for t in (state.get("node_trace") or [])]
    rag_ran = "retrieve_protocol" in nodes
    if state.get("rag_has_sources"):
        return None
    if not rag_ran:
        return "RAG não foi executado neste caminho (refuse ou bypass)"
    # RAG rodou mas não achou chunks acima do threshold
    return "Nenhum chunk passou do threshold do RAG (0.55)"


def _normalize_guardrail_summary(results: list[dict]) -> list[dict]:
    """Reduz cada GuardrailResult ao essencial pra ficha."""
    summary = []
    for r in results:
        if not r.get("triggered"):
            continue
        summary.append({
            "name": r.get("guardrail_name"),
            "level": r.get("level"),
            "applies_to": r.get("applies_to"),
            "action_taken": r.get("action_taken"),
            "severity": r.get("severity"),
            "message": r.get("message"),
        })
    return summary


def _latency_breakdown(state: MedicalState) -> dict[str, float]:
    """Latência por nó (segundos)."""
    return {
        t.get("node", "?"): t.get("latency_s", 0.0)
        for t in (state.get("node_trace") or [])
    }


def _adapter_short_name() -> str:
    """Versão curta do adapter — só o último segmento do path."""
    if not ADAPTER_PATH:
        return "(sem adapter)"
    return ADAPTER_PATH.rstrip("/").split("/")[-1]


def build_explanation(state: MedicalState) -> dict[str, Any]:
    """Decompõe o state final do grafo numa ficha estruturada de raciocínio.

    Função pura sobre `state` — não chama LLM, não tem efeitos colaterais.
    Retorna dict serializável (pronto pra JSON, pra API HTTP, pro audit DB).
    """
    patient_data = state.get("patient_data")
    pending_exams = state.get("pending_exams")
    rag_chunks = state.get("rag_chunks") or []

    explanation = {
        "request_id": state.get("request_id"),
        "classification": {
            "intent": state.get("intent"),
            "urgency": state.get("urgency"),
            "bypass_detected": bool(state.get("bypass_detected")),
        },
        "patient_used": (
            {
                "id": patient_data.get("id"),
                "fields_consulted": _patient_fields_consulted(patient_data),
            }
            if patient_data else None
        ),
        "exams_consulted": (
            [
                {
                    "tipo_exame": e.get("tipo_exame"),
                    "data_solicitacao": e.get("data_solicitacao"),
                    "prioridade": e.get("prioridade"),
                }
                for e in pending_exams
            ]
            if pending_exams else None
        ),
        "sources": [
            {
                "file": c.get("source_file"),
                "section": c.get("section"),
                "score": c.get("score"),
            }
            for c in rag_chunks
        ],
        "no_sources_reason": _no_sources_reason(state),
        "guardrails_triggered": (
            _normalize_guardrail_summary(state.get("input_guardrails_triggered") or []) +
            _normalize_guardrail_summary(state.get("output_guardrails_triggered") or [])
        ),
        "was_rewritten": any(
            r.get("action_taken") == "rewritten"
            for r in (state.get("output_guardrails_triggered") or [])
        ),
        "alerts_emitted": [
            {
                "timestamp": a.get("timestamp"),
                "patient_id": a.get("patient_id"),
                "urgency": a.get("urgency"),
                "summary": a.get("summary"),
            }
            for a in (state.get("alerts_emitted") or [])
        ],
        "errors": list(state.get("errors") or []),
        "model_info": {
            "base": MODEL_PATH,
            "adapter": _adapter_short_name(),
        },
        "latency_breakdown_s": _latency_breakdown(state),
        "total_latency_s": round(
            sum(_latency_breakdown(state).values()), 3
        ),
    }
    return explanation


# ────────────────────────────────────────────────────────────────────────
# format_explanation: dict → Rich Panel (pra demo /why)
# ────────────────────────────────────────────────────────────────────────

def _truncate(s: str | None, n: int = 80) -> str:
    if not s:
        return "—"
    return s if len(s) <= n else s[: n - 1] + "…"


def _classification_panel(exp: dict) -> Panel:
    c = exp["classification"]
    bypass = "  ⚠ bypass" if c["bypass_detected"] else ""
    body = Text(
        f"intent: {c['intent']}    urgency: {c['urgency']}{bypass}",
        style="white",
    )
    return Panel(body, title="[bold]Classificação", border_style="cyan")


def _patient_panel(exp: dict) -> Panel | None:
    p = exp.get("patient_used")
    if not p:
        return Panel(
            Text("Sem paciente consultado neste request.", style="dim"),
            title="[bold]Paciente",
            border_style="dim",
        )
    fields = ", ".join(p["fields_consulted"]) or "(nenhum)"
    body = Text(
        f"ID: {p['id']}\nCampos consultados: {fields}",
        style="white",
    )
    return Panel(body, title="[bold]Paciente", border_style="yellow")


def _exams_panel(exp: dict) -> Panel | None:
    exams = exp.get("exams_consulted")
    if not exams:
        return None
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Exame", style="cyan", no_wrap=False)
    table.add_column("Solicitação", style="dim", no_wrap=True)
    table.add_column("Prioridade", style="yellow", justify="center")
    for e in exams:
        table.add_row(e["tipo_exame"], e["data_solicitacao"], e["prioridade"])
    return Panel(table, title=f"[bold]Exames pendentes ({len(exams)})",
                 border_style="magenta")


def _sources_panel(exp: dict) -> Panel:
    sources = exp.get("sources") or []
    if not sources:
        msg = exp.get("no_sources_reason") or "Nenhuma fonte consultada."
        return Panel(Text(msg, style="dim"), title="[bold]Fontes RAG",
                     border_style="dim")
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Arquivo", style="cyan")
    table.add_column("Seção", style="magenta")
    table.add_column("Score", style="green", justify="right")
    for i, s in enumerate(sources, 1):
        table.add_row(
            str(i),
            str(s.get("file") or "?"),
            str(s.get("section") or "?"),
            f"{s.get('score', 0):.3f}",
        )
    return Panel(table, title=f"[bold]Fontes RAG ({len(sources)})",
                 border_style="green")


def _guardrails_panel(exp: dict) -> Panel:
    guards = exp.get("guardrails_triggered") or []
    if not guards:
        return Panel(Text("Nenhum guardrail disparou.", style="dim"),
                     title="[bold]Guardrails", border_style="dim")
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Guardrail", style="cyan")
    table.add_column("Side", style="dim")
    table.add_column("Level", style="dim")
    table.add_column("Sev.", justify="right", style="yellow")
    table.add_column("Ação", style="green")
    for g in guards:
        table.add_row(
            g["name"],
            g["applies_to"],
            g["level"],
            f"{g.get('severity', 0):.2f}",
            g.get("action_taken") or "—",
        )
    rewrite_note = "" if not exp.get("was_rewritten") else \
        "\n[yellow](resposta foi reescrita)[/]"
    return Panel(
        Group(table, Text.from_markup(rewrite_note)) if rewrite_note else table,
        title=f"[bold]Guardrails ({len(guards)} disparado(s))",
        border_style="red",
    )


def _alerts_panel(exp: dict) -> Panel | None:
    alerts = exp.get("alerts_emitted") or []
    if not alerts:
        return None
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Hora", style="dim", no_wrap=True)
    table.add_column("Paciente", style="yellow")
    table.add_column("Urgência", style="red")
    table.add_column("Resumo", style="white", no_wrap=False)
    for a in alerts:
        table.add_row(
            a.get("timestamp") or "?",
            a.get("patient_id") or "—",
            a.get("urgency", ""),
            _truncate(a.get("summary"), 60),
        )
    return Panel(table, title="[bold]🚨 Alertas emitidos",
                 border_style="yellow")


def _latency_panel(exp: dict) -> Panel:
    latencies = exp.get("latency_breakdown_s") or {}
    total = exp.get("total_latency_s", 0)
    if not latencies:
        return Panel(Text("Sem dados de latência.", style="dim"),
                     title="[bold]Latências", border_style="dim")
    # Ordena por duração descendente — gargalos primeiro
    items = sorted(latencies.items(), key=lambda kv: kv[1], reverse=True)
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Nó", style="cyan")
    table.add_column("Latência (s)", justify="right", style="green")
    table.add_column("% do total", justify="right", style="dim")
    for node, lat in items:
        pct = (lat / total * 100) if total > 0 else 0
        table.add_row(node, f"{lat:.3f}", f"{pct:.1f}%")
    return Panel(table, title=f"[bold]Latências (total {total:.2f}s)",
                 border_style="blue")


def _model_info_panel(exp: dict) -> Panel:
    m = exp.get("model_info", {})
    body = Text(
        f"Base: {m.get('base', '?')}\n"
        f"Adapter: {m.get('adapter', '?')}",
        style="dim",
    )
    return Panel(body, title="[bold]Modelo", border_style="dim")


def _errors_panel(exp: dict) -> Panel | None:
    errors = exp.get("errors") or []
    if not errors:
        return None
    body = "\n".join(f"• {e}" for e in errors)
    return Panel(Text(body, style="yellow"),
                 title=f"[bold]⚠ Erros não-fatais ({len(errors)})",
                 border_style="yellow")


def format_explanation(exp: dict, *, detail: bool = False):
    """Renderiza a ficha como um conjunto de painéis Rich.

    `detail=False` (default): painéis essenciais — classificação, paciente,
    fontes, guardrails, alertas.
    `detail=True`: adiciona painéis de exames, latências, modelo, erros.

    Retorna um `Group` pra `console.print()` exibir tudo.
    """
    panels: list = [
        Panel(
            Text(f"request_id: {exp.get('request_id', '?')}", style="cyan"),
            title="[bold]Ficha de raciocínio",
            border_style="cyan",
        ),
        _classification_panel(exp),
        _patient_panel(exp),
        _sources_panel(exp),
        _guardrails_panel(exp),
    ]

    alerts_p = _alerts_panel(exp)
    if alerts_p:
        panels.append(alerts_p)

    if detail:
        exams_p = _exams_panel(exp)
        if exams_p:
            panels.append(exams_p)
        panels.append(_latency_panel(exp))
        panels.append(_model_info_panel(exp))
        errors_p = _errors_panel(exp)
        if errors_p:
            panels.append(errors_p)

    return Group(*panels)
