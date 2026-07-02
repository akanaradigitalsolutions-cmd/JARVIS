# JARVIS — Architecture & Roadmap

A personal AI assistant (like Iron Man's JARVIS) that runs on your Mac or
Windows machine and helps with data analytics, digital marketing (Google
Ads, social ads), e-commerce for hospitality, web development, and general
digital work.

## Design decisions (locked in)

| Decision | Choice | Why |
|---|---|---|
| Brain | Claude API (Anthropic), tool-use/function-calling loop | Best reasoning + tool use; swappable later via `core/llm.py` |
| Interface | Voice-first (wake word + STT + TTS), with text chat as fallback/dev interface | Matches the "JARVIS" experience; text mode used for testing without a mic |
| Platform | Cross-platform desktop app (Python + PySide6/Qt) | One codebase, native installers for Mac and Windows |
| Extensibility | "Skills" plugin system | Every capability (PDF report, ads reporting, Shopify sync, ...) is a self-contained skill registered as a Claude tool |
| Workspace | Sandboxed folder (`~/Jarvis/workspace`) | Every file Jarvis creates/reads lives here — no unrestricted filesystem access |

## High-level architecture

```
                     ┌─────────────────────────┐
   mic  ──STT──▶     │                         │
                     │   Core Orchestrator     │──▶ Claude API (tool-use loop)
   text ────────────▶│  (conversation + memory)│
                     │                         │◀── tool_use blocks
   speaker ◀──TTS──  └───────────┬─────────────┘
                                 │ dispatches tool_use to
                                 ▼
                     ┌─────────────────────────┐
                     │      Skill Registry      │
                     │  (name → fn + schema)    │
                     └───────────┬─────────────┘
                 ┌───────────────┼───────────────────┬───────────────┐
                 ▼               ▼                    ▼               ▼
           filesystem       documents           data_analysis      (future:
           skill            skill (PDF/PPTX)    skill (CSV/charts)  ads, shopify,
                                                                     web-dev skills)
```

Everything (voice loop, desktop UI, CLI) is just a different **frontend**
that feeds text into the same orchestrator. The orchestrator and skills
don't know or care whether the input came from a mic or a keyboard.

## Repo layout

```
jarvis/
  core/
    config.py         # env vars, workspace path, model selection
    llm.py             # thin wrapper around the Anthropic client
    memory.py          # session persistence (JSON, on disk)
    orchestrator.py    # the agent loop: user msg -> Claude -> tool calls -> result -> ...
  skills/
    base.py            # @skill decorator + registry
    filesystem.py       # read/write/list files inside the sandboxed workspace
    documents.py         # generate_pdf_report, generate_presentation, generate_excel_report
    data_analysis.py     # load_dataset, analyze_dataset, chart generation
    (future) marketing.py, ecommerce.py, webdev.py
  voice/
    stt.py              # speech-to-text (faster-whisper, local/offline)
    tts.py              # text-to-speech (pyttsx3, offline)
    wake_word.py         # "Jarvis" wake word detection (openWakeWord)
    loop.py              # ties mic -> STT -> orchestrator -> TTS -> speaker
  ui/
    chat_window.py       # PySide6 desktop chat window w/ mic toggle
  cli.py                 # terminal chat client (always works, no audio needed)
  main.py                 # entry point: `jarvis`, `jarvis --voice`, `jarvis --ui`
```

## Roadmap (phased delivery)

- **Phase 1 — Core + first real skills (this commit)**
  Orchestrator, skill system, filesystem skill, document generation
  (PDF/PPTX/Excel), data analysis skill, CLI chat. Fully working and
  testable without any special hardware.

- **Phase 1.5 — Voice + Desktop UI (this commit, code complete)**
  STT/TTS/wake-word modules and a PySide6 chat window, wired into the same
  orchestrator. Needs to be tested on your actual Mac/Windows machine
  (this build sandbox has no mic/speaker/display).

- **Phase 2 — Digital marketing skills**
  Google Ads API + Meta (Facebook/Instagram) Ads API skills: pull
  performance reports, flag underperforming campaigns, suggest budget
  changes. Requires your API credentials (OAuth apps) — we'll set these up
  together when we get there.

- **Phase 3 — E-commerce for hospitality**
  Shopify/WooCommerce (or your specific platform) skill: orders, bookings,
  inventory, revenue summaries, automated reporting.

- **Phase 4 — Web developer helper**
  Project scaffolding, git operations, deployment helpers, local dev
  server management.

- **Phase 5 — Memory & personalization**
  Long-term memory (facts about you/your business persisted across
  sessions), scheduled/recurring tasks ("every Monday, email me last
  week's ad performance"), proactive notifications.

- **Phase 6 — Packaging**
  PyInstaller-based `.app` (Mac) and `.exe` (Windows) installers, auto
  updater. Must be built on the target OS.

Each phase after Phase 1.5 will be its own set of commits so we can test
and adjust before moving on.

## Security notes

- API keys live in a local `.env` file (gitignored), never committed.
- The filesystem skill can only read/write inside `~/Jarvis/workspace` —
  path traversal outside that folder is blocked.
- Voice wake-word detection runs fully locally/offline; only your actual
  spoken commands (after the wake word) are sent to the STT engine, and
  only the transcribed text is sent to the Claude API.
