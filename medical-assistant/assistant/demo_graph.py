"""Demo interativo do grafo LangGraph — Fase 5.

Diferenças do `demo_chat.py` (Fase 4):
- Orquestra via grafo (StateGraph) em vez de chain LCEL.
- Mostra cada nó executando em tempo real (ícone + latência + resumo).
- Comandos extras: /trace, /state, /alerts.
- `demo_chat.py` continua existindo como referência da Fase 4.

Comandos:
    /trace          tabela com os nós executados na última pergunta
    /state          JSON com o estado completo da última pergunta
    /alerts         alertas emitidos NESTA sessão (gravados em alerts.jsonl)
    /why            ficha de raciocínio (Fase 6, Bloco 3) — resumo
    /why detail     ficha completa (com latências, exames, modelo, erros)
    /clear          limpa a tela / último trace
    /exit           sai

Uso:
    uv run python assistant/demo_graph.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from assistant.graph import run_medical_graph
from assistant.graph_nodes import ALERTS_LOG_PATH
from assistant.graph_state import MedicalState

console = Console()

# Ícones por nó — pra deixar o output legível no vídeo.
NODE_ICONS = {
    "classify_intent": "🎯",
    "triage_urgency": "🚦",
    "fetch_patient_data": "👤",
    "check_pending_exams": "🧪",
    "retrieve_protocol": "📚",
    "generate_response": "💭",
    "guardrail_check": "🛡️",
    "emit_alert_if_needed": "🚨",
    "finalize_response": "✅",
    "refuse_node": "🚫",
    "rewrite_node": "✏️",
}


class GraphNodeLogHandler(logging.Handler):
    """Handler que escuta logs do `assistant.graph_nodes` e imprime em
    tempo real um resumo do nó quando ele LOGA com nível INFO/WARNING.

    Mais simples que `astream` do LangGraph e suficiente pro demo.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            return
        # Filtra logs que começam com [nome_do_no] — convenção dos nós
        if not msg.startswith("["):
            return
        end = msg.find("]")
        if end < 2:
            return
        node = msg[1:end]
        if node not in NODE_ICONS:
            return
        icon = NODE_ICONS[node]
        rest = msg[end + 1:].strip()
        # Cor por nível
        color = "white"
        if record.levelno >= logging.WARNING:
            color = "yellow"
        console.print(f"  [{color}]{icon} {node:<22s} {rest}[/]")


def _setup_realtime_logging() -> None:
    """Configura o logger pra imprimir cada nó conforme executa."""
    h = GraphNodeLogHandler(level=logging.INFO)
    nodes_logger = logging.getLogger("assistant.graph_nodes")
    nodes_logger.setLevel(logging.INFO)
    # Remove handlers existentes pra evitar duplicação se rerodar
    for existing in list(nodes_logger.handlers):
        nodes_logger.removeHandler(existing)
    nodes_logger.addHandler(h)
    nodes_logger.propagate = False


def _print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Assistente clínico — Demo Fase 5 (LangGraph)[/]\n"
            "Qwen2.5-1.5B + LoRA + LangGraph (9 nós) + RAG + SQLite\n"
            "[dim]Cada nó imprime quando executa. Veja /trace para detalhes.[/]\n\n"
            "[yellow]Comandos:[/] /trace /state /alerts /why [detail] /clear /exit\n"
            "[dim]Dica: para incluir paciente, mencione o ID na pergunta (ex: P0001).[/]",
            border_style="cyan",
        )
    )


def _render_trace(state: MedicalState) -> None:
    trace = state.get("node_trace") or []
    if not trace:
        console.print("[dim]Sem trace na última pergunta.[/]")
        return
    table = Table(title="Trace do último request", show_lines=False, expand=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Nó", style="cyan")
    table.add_column("Latência", justify="right", style="green")
    table.add_column("Resumo", style="white")
    table.add_column("Erro", style="red")
    for i, e in enumerate(trace, start=1):
        icon = NODE_ICONS.get(e["node"], "•")
        table.add_row(
            str(i),
            f"{icon} {e['node']}",
            f"{e['latency_s']:.3f}s",
            e["summary"],
            e.get("error") or "",
        )
    console.print(table)


def _render_state(state: MedicalState) -> None:
    # Serializa só o essencial pra ficar legível
    summary = {
        "question": state.get("question"),
        "patient_id": state.get("patient_id"),
        "intent": state.get("intent"),
        "urgency": state.get("urgency"),
        "patient_data": state.get("patient_data"),
        "pending_exams": state.get("pending_exams"),
        "rag_has_sources": state.get("rag_has_sources"),
        "rag_chunks": [
            {k: v for k, v in c.items() if k != "text"}  # omite texto longo
            for c in (state.get("rag_chunks") or [])
        ],
        "draft_response_preview": (state.get("draft_response") or "")[:200],
        "guardrail_flags": state.get("guardrail_flags"),
        "was_rewritten": state.get("was_rewritten"),
        "final_response_preview": (state.get("final_response") or "")[:300],
        "alerts_emitted": state.get("alerts_emitted"),
        "errors": state.get("errors"),
        "node_trace_count": len(state.get("node_trace") or []),
    }
    console.print(JSON(json.dumps(summary, ensure_ascii=False, default=str)))


def _render_session_alerts(session_start: str) -> None:
    """Lê alerts.jsonl e mostra os emitidos desde o início da sessão."""
    if not ALERTS_LOG_PATH.exists():
        console.print("[dim]Nenhum alerta emitido ainda nesta sessão.[/]")
        return
    rows = []
    with ALERTS_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get("timestamp", "") >= session_start:
                    rows.append(d)
            except json.JSONDecodeError:
                continue
    if not rows:
        console.print("[dim]Nenhum alerta emitido nesta sessão.[/]")
        return
    table = Table(title="Alertas emitidos nesta sessão",
                  show_lines=False, expand=True)
    table.add_column("Hora", style="dim")
    table.add_column("Paciente", style="yellow")
    table.add_column("Pergunta", style="white", no_wrap=False)
    table.add_column("Resumo", style="dim", no_wrap=False)
    for r in rows:
        table.add_row(
            r.get("timestamp", "?"),
            r.get("patient_id") or "—",
            (r.get("question") or "")[:60],
            (r.get("summary") or "")[:80],
        )
    console.print(table)


def main() -> int:
    _setup_realtime_logging()

    console.print("[dim]Carregando modelo, índice RAG e banco de pacientes...[/]")
    console.print("[dim](pode levar ~10s na primeira execução)[/]\n")

    # Force build no startup pra "esquentar" o modelo (1ª query fica rápida)
    from assistant.graph import _get_graph
    _get_graph()
    console.print("[green]✓[/] Tudo pronto.\n")

    _print_banner()
    last_state: Optional[MedicalState] = None
    session_start = datetime.now().isoformat(timespec="seconds")

    while True:
        try:
            user_input = console.input("\n[bold magenta]Você:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nAté.")
            return 0

        if not user_input:
            continue
        cmd_low = user_input.lower()

        # ─── Comandos ────────────────────────────────────────────────────
        if cmd_low in ("/exit", "/quit", "/sair"):
            console.print("Até.")
            return 0
        if cmd_low == "/clear":
            console.clear()
            _print_banner()
            last_state = None
            continue
        if cmd_low == "/trace":
            if not last_state:
                console.print("[dim]Faça uma pergunta primeiro.[/]")
                continue
            _render_trace(last_state)
            continue
        if cmd_low == "/state":
            if not last_state:
                console.print("[dim]Faça uma pergunta primeiro.[/]")
                continue
            _render_state(last_state)
            continue
        if cmd_low == "/alerts":
            _render_session_alerts(session_start)
            continue
        if cmd_low == "/why" or cmd_low.startswith("/why "):
            if not last_state:
                console.print("[dim]Faça uma pergunta primeiro.[/]")
                continue
            from assistant.explainability import (
                build_explanation,
                format_explanation,
            )
            detail = cmd_low.startswith("/why detail")
            exp = build_explanation(last_state)
            console.print(format_explanation(exp, detail=detail))
            continue

        # ─── Inferência ────────────────────────────────────────────────────
        # Extrai patient_id se for prefix-style: "@P0001 pergunta..."
        # Senão, deixa o Nó 3 extrair via regex da própria pergunta.
        patient_id = None
        question = user_input

        console.print(f"\n[bold]→ Executando grafo...[/]")
        t0 = time.monotonic()
        try:
            state = run_medical_graph(question=question, patient_id=patient_id)
        except KeyboardInterrupt:
            console.print("\n[dim](geração interrompida)[/]")
            continue
        total = time.monotonic() - t0
        last_state = state

        # ─── Render da resposta ────────────────────────────────────────────
        console.print()
        console.print(
            f"[bold green]Assistente[/] [dim](total {total:.2f}s, "
            f"intent={state.get('intent')}, urgency={state.get('urgency')})[/]"
        )
        resp = state.get("final_response") or "(sem resposta)"
        console.print(Markdown(resp))
        # Aviso visível se houve erros (não-fatais) ou rewrite
        if state.get("errors"):
            console.print(f"[yellow](nota: {len(state['errors'])} erro(s) "
                          "não-fatal(is); veja /trace)[/]")
        if state.get("was_rewritten"):
            console.print("[yellow](nota: resposta foi reescrita pelo guardrail)[/]")


if __name__ == "__main__":
    sys.exit(main())
