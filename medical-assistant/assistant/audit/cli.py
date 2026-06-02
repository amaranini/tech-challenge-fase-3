"""CLI de auditoria — consulta o audit DB (Fase 6, Bloco 2).

Subcomandos:
- list   [--last N]                          últimas N interações
- show   <request_id>                        detalhe completo
- filter [--patient X | --has-alerts |
          --has-guardrail | --guardrail NAME |
          --since DATE]                       filtros
- stats                                      agregados
- tail   [--interval N]                      polling ao vivo (Ctrl+C sai)
- export <request_id> [--out FILE]           dump JSON
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from assistant.audit.reader import (
    AuditReader,
    GuardrailEventRow,
    InteractionDetail,
    InteractionRow,
)
from assistant.audit.schema import AUDIT_DB_PATH

console = Console()


# ────────────────────────────────────────────────────────────────────────
# Helpers de formatação
# ────────────────────────────────────────────────────────────────────────

def _truncate(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _render_interactions_table(rows: list[InteractionRow], title: str = "Interações") -> None:
    if not rows:
        console.print("[dim](nenhuma interação encontrada)[/]")
        return
    table = Table(title=title, expand=True, show_lines=False)
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Quando", style="dim", no_wrap=True)
    table.add_column("Request ID", style="cyan", no_wrap=False)
    table.add_column("Pergunta", style="white", no_wrap=False)
    table.add_column("Paciente", style="yellow", no_wrap=True)
    table.add_column("Intent", style="dim")
    table.add_column("Urg.", style="dim")
    table.add_column("Bypass", style="red", justify="center")
    table.add_column("Lat (ms)", justify="right", style="green")
    for r in rows:
        table.add_row(
            str(r.id),
            r.ts,
            r.request_id[:8] + "…",
            _truncate(r.question, 50),
            r.patient_id or "—",
            r.intent or "—",
            r.urgency or "—",
            "⚠" if r.bypass_detected else "·",
            str(r.latency_ms) if r.latency_ms else "—",
        )
    console.print(table)


def _render_guardrail_events_table(events: list[GuardrailEventRow]) -> None:
    if not events:
        return
    triggered = [e for e in events if e.triggered]
    not_triggered = [e for e in events if not e.triggered]
    if triggered:
        table = Table(title=f"Guardrails que dispararam ({len(triggered)})",
                      expand=True, show_lines=False)
        table.add_column("Nome", style="cyan")
        table.add_column("Side", style="dim")
        table.add_column("Level", style="dim")
        table.add_column("Severity", justify="right", style="yellow")
        table.add_column("Mensagem", style="white", no_wrap=False)
        table.add_column("Ação", style="green")
        for e in triggered:
            table.add_row(
                e.guardrail_name,
                e.applies_to,
                e.level,
                f"{e.severity:.2f}",
                _truncate(e.message, 60),
                e.action_taken or "—",
            )
        console.print(table)
    if not_triggered:
        names = ", ".join(e.guardrail_name for e in not_triggered)
        console.print(f"[dim]Guardrails sem disparo ({len(not_triggered)}): {names}[/]")


# ────────────────────────────────────────────────────────────────────────
# Handlers dos subcomandos
# ────────────────────────────────────────────────────────────────────────

def cmd_list(args, reader: AuditReader) -> int:
    rows = reader.list_recent(limit=args.last)
    _render_interactions_table(rows, title=f"Últimas {args.last} interações")
    return 0


def cmd_show(args, reader: AuditReader) -> int:
    # Permite shortcut: passar prefixo do request_id (primeiros chars)
    rid = args.request_id
    detail = reader.get_by_id(rid)
    if detail is None:
        # Tenta prefixo
        for r in reader.list_recent(100):
            if r.request_id.startswith(rid):
                detail = reader.get_by_id(r.request_id)
                break
    if detail is None:
        console.print(f"[red]Interação não encontrada: {rid}[/]")
        return 1

    i = detail.interaction
    # Cabeçalho
    header = (
        f"[bold]{i.request_id}[/]\n"
        f"[dim]{i.ts}  •  intent={i.intent}  •  urgency={i.urgency}  •  "
        f"latency={i.latency_ms}ms[/]\n"
        f"[bold]Pergunta:[/] {i.question}"
    )
    if i.patient_id:
        header += f"\n[bold]Paciente:[/] {i.patient_id}"
    if i.bypass_detected:
        header += "\n[red]⚠ BYPASS DETECTADO NO INPUT[/]"
    console.print(Panel(header, border_style="cyan"))

    if i.response:
        console.print(Panel(i.response, title="[bold]Resposta final", border_style="green"))

    _render_guardrail_events_table(detail.guardrail_events)

    if detail.alerts:
        table = Table(title=f"Alertas ({len(detail.alerts)})", expand=True)
        table.add_column("Quando", style="dim")
        table.add_column("Urgência", style="red")
        table.add_column("Resumo", style="white")
        table.add_column("Ack?", justify="center", style="dim")
        for a in detail.alerts:
            table.add_row(a.ts, a.urgency, _truncate(a.summary, 80),
                          "✓" if a.acknowledged else "·")
        console.print(table)

    if detail.rag_retrievals:
        for rag in detail.rag_retrievals:
            sub = Table(title=f"RAG retrieval (had_sources={rag['had_sources']})",
                        expand=True)
            sub.add_column("#", justify="right", style="dim")
            sub.add_column("Source", style="cyan")
            sub.add_column("Section", style="magenta")
            sub.add_column("Score", justify="right", style="green")
            for k, c in enumerate(rag["top_k_results"], 1):
                sub.add_row(
                    str(k),
                    str(c.get("source_file") or "—"),
                    str(c.get("section") or "—"),
                    f"{c.get('score', 0):.3f}",
                )
            console.print(sub)

    return 0


def cmd_filter(args, reader: AuditReader) -> int:
    if args.patient:
        rows = reader.filter_by_patient(args.patient, limit=args.limit)
        _render_interactions_table(rows, title=f"Interações para paciente {args.patient}")
    elif args.has_alerts:
        rows = reader.filter_has_alerts(limit=args.limit)
        _render_interactions_table(rows, title="Interações com alerta")
    elif args.has_guardrail:
        rows = reader.filter_has_guardrail(limit=args.limit)
        _render_interactions_table(rows, title="Interações com guardrail disparado")
    elif args.guardrail:
        rows = reader.filter_by_guardrail(args.guardrail, limit=args.limit)
        _render_interactions_table(rows, title=f"Interações com '{args.guardrail}' disparado")
    elif args.since:
        rows = reader.since(args.since, limit=args.limit)
        _render_interactions_table(rows, title=f"Interações desde {args.since}")
    else:
        console.print("[red]Forneça pelo menos um filtro. Veja --help.[/]")
        return 2
    return 0


def cmd_stats(args, reader: AuditReader) -> int:
    s = reader.stats()
    table = Table(title="Estatísticas do audit DB", show_lines=False)
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", justify="right", style="white")
    table.add_row("Total de interações", str(s["total_interactions"]))
    table.add_row("Com guardrail disparado", str(s["with_guardrail_triggered"]))
    table.add_row("Com alerta emitido", str(s["with_alert"]))
    table.add_row("Tentativas de bypass", str(s["bypass_attempts"]))
    table.add_row("Latência média (ms)", str(s["avg_latency_ms"]))
    console.print(table)

    if s["by_intent"]:
        sub = Table(title="Por intent", show_lines=False)
        sub.add_column("Intent", style="cyan")
        sub.add_column("Count", justify="right")
        for k, v in s["by_intent"].items():
            sub.add_row(k, str(v))
        console.print(sub)
    if s["by_urgency"]:
        sub = Table(title="Por urgency", show_lines=False)
        sub.add_column("Urgency", style="cyan")
        sub.add_column("Count", justify="right")
        for k, v in s["by_urgency"].items():
            sub.add_row(k, str(v))
        console.print(sub)
    if s["by_guardrail"]:
        sub = Table(title="Disparos por guardrail", show_lines=False)
        sub.add_column("Guardrail", style="cyan")
        sub.add_column("Disparos", justify="right")
        for k, v in s["by_guardrail"].items():
            sub.add_row(k, str(v))
        console.print(sub)
    return 0


def cmd_tail(args, reader: AuditReader) -> int:
    """Polling ao vivo: a cada `interval`s, busca interações com id > last_seen."""
    interval = args.interval
    # Começa do estado atual: pega a maior id corrente como cursor
    last_rows = reader.list_recent(1)
    last_seen = last_rows[0].id if last_rows else 0
    console.print(
        f"[dim]Tail iniciado — cursor em id={last_seen}, "
        f"interval={interval}s. Ctrl+C pra sair.[/]"
    )
    try:
        while True:
            new = reader.tail_since(last_seen, limit=20)
            for r in new:
                console.print()
                _render_interactions_table([r], title=f"Nova interação #{r.id}")
                last_seen = max(last_seen, r.id)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Tail encerrado.[/]")
    return 0


def cmd_export(args, reader: AuditReader) -> int:
    detail = reader.get_by_id(args.request_id)
    if detail is None:
        # Tenta prefixo
        for r in reader.list_recent(100):
            if r.request_id.startswith(args.request_id):
                detail = reader.get_by_id(r.request_id)
                break
    if detail is None:
        console.print(f"[red]Interação não encontrada: {args.request_id}[/]")
        return 1

    # Serialização defensiva: dataclass → dict via __dict__
    payload = {
        "interaction": detail.interaction.__dict__,
        "guardrail_events": [e.__dict__ for e in detail.guardrail_events],
        "alerts": [a.__dict__ for a in detail.alerts],
        "rag_retrievals": detail.rag_retrievals,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(serialized, encoding="utf-8")
        console.print(f"[green]✓ Exportado para {args.out}[/]")
    else:
        console.print(JSON(serialized))
    return 0


# ────────────────────────────────────────────────────────────────────────
# Parser
# ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="assistant.audit",
        description="Consulta o audit DB do assistente clínico (Fase 6).",
    )
    parser.add_argument(
        "--db", default=None,
        help=f"Path do audit DB (default: {AUDIT_DB_PATH.relative_to(Path.cwd()) if AUDIT_DB_PATH.is_relative_to(Path.cwd()) else AUDIT_DB_PATH})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Últimas N interações")
    p_list.add_argument("--last", type=int, default=10)

    p_show = sub.add_parser("show", help="Detalhe completo de uma interação")
    p_show.add_argument("request_id", help="UUID ou prefixo")

    p_filter = sub.add_parser("filter", help="Filtros")
    p_filter.add_argument("--patient", help="ID do paciente")
    p_filter.add_argument("--has-alerts", action="store_true")
    p_filter.add_argument("--has-guardrail", action="store_true")
    p_filter.add_argument("--guardrail", help="Nome do guardrail")
    p_filter.add_argument("--since", help="Data ISO (ex: 2026-06-01)")
    p_filter.add_argument("--limit", type=int, default=50)

    sub.add_parser("stats", help="Estatísticas agregadas")

    p_tail = sub.add_parser("tail", help="Observa novas interações ao vivo")
    p_tail.add_argument("--interval", type=float, default=2.0,
                        help="Segundos entre polls (default 2)")

    p_export = sub.add_parser("export", help="Exporta uma interação como JSON")
    p_export.add_argument("request_id")
    p_export.add_argument("--out", help="Arquivo de saída (default stdout)")

    args = parser.parse_args()
    db_path = Path(args.db) if args.db else AUDIT_DB_PATH
    reader = AuditReader(db_path)

    handlers = {
        "list": cmd_list, "show": cmd_show, "filter": cmd_filter,
        "stats": cmd_stats, "tail": cmd_tail, "export": cmd_export,
    }
    return handlers[args.cmd](args, reader)


if __name__ == "__main__":
    sys.exit(main())
