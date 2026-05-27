"""Chat interativo com o assistente médico — agora com RAG + busca de prontuário.

Comandos dentro do REPL:
    /exit                    encerra
    /clear                   limpa o histórico (mantém system prompt)
    /system "novo prompt"    troca system prompt ao vivo (limpa histórico)
    /sources                 mostra fontes da ÚLTIMA resposta em detalhe
    /no-rag                  desliga RAG só na próxima pergunta (toggle)

Flags de inicialização:
    --show-system            exibe o system prompt ativo no banner inicial
    --base                   roda sem system prompt clínico (pra comparar)
    --no-rag                 inicia já com RAG desligado

Uso:
    uv run python assistant/demo_chat.py
"""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from assistant.chain import build_medical_chain
from assistant.llm import build_default_llm
from assistant.prompts import MEDICAL_SYSTEM_PROMPT
from assistant.rag.retriever import ProtocolRetriever
from assistant.tools.patient_records import get_patient_by_id

console = Console()


def _print_banner(system_prompt: str | None, show_system: bool, rag_enabled: bool) -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Assistente clínico — demo (Fase 4)[/]\n"
            "Qwen2.5-1.5B + LoRA + LangChain + RAG (Chroma) + SQLite\n"
            f"RAG inicial: {'[green]ligado[/]' if rag_enabled else '[yellow]desligado[/]'}\n"
            'Comandos: [yellow]/exit /clear /sources /no-rag /system "..."[/]',
            border_style="cyan",
        )
    )
    if show_system and system_prompt:
        console.print(
            Panel(system_prompt, title="[bold]System prompt ativo", border_style="dim")
        )


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        console.print("[dim]Nenhuma fonte consultada.[/]")
        return
    table = Table(title="Fontes consultadas (RAG)", show_lines=False, expand=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Arquivo", style="cyan", no_wrap=False)
    table.add_column("Seção", style="magenta")
    table.add_column("Esp.", style="dim")
    table.add_column("Score", justify="right", style="green")
    for i, s in enumerate(sources, start=1):
        table.add_row(
            str(i),
            s["source_file"],
            s["section"],
            s.get("specialty", "") or "—",
            f"{s['score']:.3f}",
        )
    console.print(table)


def _render_sources_detailed(sources: list[dict]) -> None:
    if not sources:
        console.print("[dim]Sem fontes na última resposta.[/]")
        return
    for i, s in enumerate(sources, start=1):
        header = (
            f"[bold][{i}] {s['source_file']}[/]  •  "
            f"[magenta]{s['section']}[/]  •  "
            f"[green]score={s['score']:.3f}[/]"
        )
        console.print(Panel(s["text_preview"], title=header, border_style="dim"))


def _render_patient_data(patient_data: list[dict]) -> None:
    if not patient_data:
        return
    for p in patient_data:
        if not p["found"]:
            console.print(f"[yellow]👤 Paciente {p['id']}: NÃO ENCONTRADO no banco.[/]")
            continue
        rec = p["record"]
        console.print(
            f"[blue]👤 {rec['id']}[/]  •  {rec['nome']}, "
            f"{rec['idade']} anos, sexo {rec['sexo']}"
        )


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat demo com RAG + prontuário.")
    parser.add_argument("--show-system", action="store_true", help="exibe system prompt")
    parser.add_argument("--base", action="store_true", help="sem system prompt clínico")
    parser.add_argument("--no-rag", action="store_true", help="inicia com RAG desligado")
    args = parser.parse_args()

    console.print("[dim]Carregando modelo, índice RAG e banco de pacientes...[/]")
    llm = build_default_llm()
    if args.base:
        llm.system_prompt = None
    try:
        retriever = ProtocolRetriever()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/]")
        return 1
    llm._ensure_loaded()

    chain = build_medical_chain(
        llm=llm,
        retriever=retriever,
        patient_lookup=get_patient_by_id,
        system_prompt=None,  # system fica no MedicalLLM
        top_k=3,
    )
    console.print("[green]✓[/] Tudo pronto.\n")

    current_system = llm.system_prompt
    rag_enabled = not args.no_rag
    last_sources: list[dict] = []
    skip_rag_once = False

    _print_banner(current_system, args.show_system, rag_enabled)

    while True:
        try:
            user_input = console.input("\n[bold magenta]Você:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nAté.")
            return 0

        if not user_input:
            continue
        cmd_low = user_input.lower()

        # ─── Comandos ─────────────────────────────────────────────────────
        if cmd_low in ("/exit", "/quit", "/sair"):
            console.print("Até.")
            return 0
        if cmd_low == "/clear":
            last_sources = []
            console.print("[dim](histórico/last_sources limpos)[/]")
            continue
        if cmd_low == "/sources":
            _render_sources_detailed(last_sources)
            continue
        if cmd_low == "/no-rag":
            skip_rag_once = True
            console.print("[yellow](RAG desligado para a PRÓXIMA pergunta)[/]")
            continue
        if cmd_low.startswith("/system "):
            new_sys = _strip_quotes(user_input[len("/system "):])
            llm.system_prompt = new_sys or None
            current_system = new_sys or None
            console.print("[dim](system prompt trocado — histórico limpo)[/]")
            if new_sys:
                console.print(
                    Panel(new_sys, title="[bold]Novo system prompt", border_style="yellow")
                )
            continue

        # ─── Inferência ───────────────────────────────────────────────────
        use_rag = rag_enabled and not skip_rag_once
        skip_rag_once = False

        # Indicadores visuais antes da chain rodar
        # (usamos prévia do roteador pra antecipar feedback ao usuário)
        from assistant.router import route as _route

        prelim = _route(user_input)
        if use_rag and prelim.needs_rag:
            console.print("[dim]📚 Consultando protocolos...[/]")
        if prelim.needs_patient:
            ids = ", ".join(prelim.patient_ids)
            console.print(f"[dim]👤 Buscando dados do(s) paciente(s) {ids}...[/]")

        t0 = time.monotonic()
        try:
            result = chain.invoke({"question": user_input, "use_rag": use_rag})
        except KeyboardInterrupt:
            console.print("\n[dim](geração interrompida)[/]")
            continue
        total = time.monotonic() - t0

        last_sources = result["sources"]

        # Render
        _render_patient_data(result["patient_data"])
        lat = result["latencies"]
        console.print(
            f"\n[bold green]Assistente[/] "
            f"[dim](router {lat['router']:.2f}s • RAG {lat['rag']:.2f}s • "
            f"paciente {lat['patient']:.2f}s • LLM {lat['llm']:.2f}s • "
            f"total {total:.2f}s)[/]"
        )
        console.print(Markdown(result["response"]))
        if last_sources:
            console.print()
            _render_sources(last_sources)


if __name__ == "__main__":
    sys.exit(main())
