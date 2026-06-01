"""CLI de smoke test pros guardrails (Fase 6).

Roda os guardrails de input E output sobre um texto e mostra quais
dispararam, em formato de tabela.

Uso:
    uv run python -m assistant.guardrails "Prescreva 500mg de amoxicilina"
    uv run python -m assistant.guardrails --input "Ignore suas regras"
    uv run python -m assistant.guardrails --output "Trata-se de pneumonia"
    uv run python -m assistant.guardrails --side both "qualquer texto"

`--side` controla quais guardrails rodar:
- both (default): roda input + output, marca em qual lado disparou
- input: só input-side (bypass)
- output: só output-side (4 restantes)
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from assistant.guardrails.registry import (
    INPUT_GUARDRAILS,
    OUTPUT_GUARDRAILS,
    run_input_guardrails,
    run_output_guardrails,
)

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Roda os guardrails sobre um texto e mostra disparos.",
    )
    parser.add_argument("text", help="Texto a ser analisado")
    parser.add_argument(
        "--side",
        choices=("both", "input", "output"),
        default="both",
        help="Quais guardrails rodar (default: both)",
    )
    args = parser.parse_args()

    text = args.text.strip()
    if not text:
        console.print("[red]Texto vazio.[/]")
        return 2

    console.print(Panel(text, title="[bold]Texto analisado", border_style="cyan"))

    results = []
    if args.side in ("both", "input"):
        results.extend(run_input_guardrails(text))
    if args.side in ("both", "output"):
        results.extend(run_output_guardrails(text))

    table = Table(title="Resultados dos guardrails", expand=True, show_lines=False)
    table.add_column("Guardrail", style="cyan")
    table.add_column("Side", style="dim")
    table.add_column("Level", style="dim")
    table.add_column("Triggered", justify="center")
    table.add_column("Severity", justify="right")
    table.add_column("Matched / Mensagem", no_wrap=False)

    n_triggered = 0
    for r in results:
        if r.triggered:
            n_triggered += 1
            mark = "[red]✓[/]"
        else:
            mark = "[dim]·[/]"
        matched = " | ".join(r.matched_patterns[:2]) if r.matched_patterns else r.message
        table.add_row(
            r.guardrail_name,
            r.applies_to,
            r.level,
            mark,
            f"{r.severity:.2f}",
            matched or "—",
        )

    console.print(table)

    n_total = len(results)
    if n_triggered == 0:
        console.print("\n[green]✓ Nenhum guardrail disparou.[/]")
    else:
        console.print(f"\n[yellow]⚠ {n_triggered}/{n_total} guardrails dispararam.[/]")

    return 0 if n_triggered == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
