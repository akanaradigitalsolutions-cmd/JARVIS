"""Terminal chat client. Always works — no microphone, speaker, or GUI
required — so it's the fastest way to test the orchestrator and skills.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from jarvis.core.llm import MissingApiKeyError
from jarvis.core.memory import SessionMemory
from jarvis.core.orchestrator import Orchestrator

console = Console()


def run() -> None:
    console.print("[bold cyan]JARVIS[/bold cyan] — type your request, or 'exit' to quit.\n")

    try:
        orchestrator = Orchestrator(memory=SessionMemory())
    except MissingApiKeyError as exc:
        console.print(f"[bold red]Setup needed:[/bold red] {exc}")
        return

    while True:
        try:
            user_text = console.input("[bold green]you>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        with console.status("[dim]thinking...[/dim]", spinner="dots"):
            try:
                reply = orchestrator.handle_message(user_text)
            except Exception as exc:  # noqa: BLE001 - keep the chat loop alive on errors
                console.print(f"[bold red]Error:[/bold red] {exc}")
                continue

        console.print("[bold cyan]jarvis>[/bold cyan]")
        console.print(Markdown(reply or "(no response)"))
        console.print()


if __name__ == "__main__":
    run()
