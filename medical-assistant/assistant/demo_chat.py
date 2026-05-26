"""Chat interativo com o MedicalLLM via terminal (rich).

Diferenças vs `finetuning/chat.py` (antigo, mantido):
- Usa o wrapper `MedicalLLM` (BaseChatModel do LangChain).
- System prompt clínico aplicado automaticamente.
- Output com formatação `rich` (banners, painéis, markdown render).
- Comandos:
    /exit                — encerra.
    /clear               — limpa o histórico (preserva system).
    /system "novo prompt" — troca system prompt ao vivo (limpa histórico).

Uso:
    uv run python assistant/demo_chat.py
    uv run python assistant/demo_chat.py --show-system
    uv run python assistant/demo_chat.py --base       # sem system prompt
"""

from __future__ import annotations

import argparse
import sys
import time

from langchain_core.messages import BaseMessage, HumanMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from assistant.llm import build_default_llm
from assistant.prompts import MEDICAL_SYSTEM_PROMPT

console = Console()


def _print_banner(system_prompt: str | None, show_system: bool) -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Assistente clínico — demo (Fase 3)[/]\n"
            "Modelo: Qwen2.5-1.5B + adapter LoRA + wrapper LangChain\n"
            'Comandos: [yellow]/exit[/]  [yellow]/clear[/]  [yellow]/system "novo prompt"[/]',
            border_style="cyan",
        )
    )
    if show_system and system_prompt:
        console.print(
            Panel(
                system_prompt,
                title="[bold]System prompt ativo",
                border_style="dim",
            )
        )


def _print_assistant(text: str, elapsed: float) -> None:
    console.print(f"\n[bold green]Assistente[/] [dim]({elapsed:.1f}s)[/]")
    console.print(Markdown(text))


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat demo com o MedicalLLM.")
    parser.add_argument(
        "--show-system",
        action="store_true",
        help="Mostra o system prompt ativo no banner inicial.",
    )
    parser.add_argument(
        "--base",
        action="store_true",
        help="Roda sem system prompt clínico (compara com a versão padrão).",
    )
    args = parser.parse_args()

    console.print("[dim]Carregando modelo + adapter (1ª vez pode demorar)...[/]")
    llm = build_default_llm()
    if args.base:
        llm.system_prompt = None
    llm._ensure_loaded()
    console.print("[green]✓[/] Modelo pronto.\n")

    current_system = llm.system_prompt
    _print_banner(current_system, args.show_system)

    history: list[BaseMessage] = []  # sem SystemMessage; o llm prepend o seu

    while True:
        try:
            user_input = console.input("\n[bold magenta]Você:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nAté.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit", "/sair"):
            console.print("Até.")
            return 0
        if user_input.lower() == "/clear":
            history = []
            console.print("[dim](histórico limpo)[/]")
            continue
        if user_input.lower().startswith("/system "):
            new_sys = _strip_quotes(user_input[len("/system "):])
            llm.system_prompt = new_sys or None
            history = []
            console.print("[dim](system prompt trocado — histórico limpo)[/]")
            if new_sys:
                console.print(
                    Panel(
                        new_sys,
                        title="[bold]Novo system prompt",
                        border_style="yellow",
                    )
                )
            else:
                console.print("[yellow](system prompt removido — modo base)[/]")
            continue

        history.append(HumanMessage(content=user_input))

        t0 = time.monotonic()
        try:
            response = llm.invoke(history)
        except KeyboardInterrupt:
            console.print("\n[dim](geração interrompida)[/]")
            history.pop()
            continue
        elapsed = time.monotonic() - t0

        history.append(response)
        _print_assistant(response.content, elapsed)


if __name__ == "__main__":
    sys.exit(main())
