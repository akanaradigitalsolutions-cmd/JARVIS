"""Entry point: `jarvis` (text chat), `jarvis --voice`, `jarvis --ui`."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Your personal AI assistant.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--voice", action="store_true", help="Voice mode: wake word + speech in/out.")
    mode.add_argument("--ui", action="store_true", help="Launch the animated HUD desktop window.")
    args = parser.parse_args()

    if args.voice:
        try:
            from jarvis.voice.loop import run as run_voice
        except (ImportError, OSError) as exc:
            print(
                "Voice mode isn't ready to run. Make sure you've installed the extras "
                "and have a working microphone:\n"
                "  pip install -e '.[voice]'\n"
                f"(reason: {exc})",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        run_voice()
    elif args.ui:
        try:
            from jarvis.ui.hud_window import run as run_ui
        except (ImportError, OSError) as exc:
            print(
                "The desktop UI isn't ready to run. Make sure you've installed the extras:\n"
                "  pip install -e '.[ui]'\n"
                f"(reason: {exc})",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        run_ui()
    else:
        from jarvis.cli import run as run_cli

        run_cli()


if __name__ == "__main__":
    main()
