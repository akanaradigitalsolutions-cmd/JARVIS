# JARVIS — Architecture & Roadmap

A personal AI assistant (like Iron Man's JARVIS) that runs on your Mac or
Windows machine and helps with data analytics, digital marketing (Google
Ads, social ads), e-commerce for hospitality, web development, and general
digital work.

## Design decisions (locked in)

| Decision | Choice | Why |
|---|---|---|
| Brain | The `claude` CLI (Claude Code) in headless mode, authenticated via `claude login` against a Claude Pro/Max subscription | Reuses usage already included in the subscription instead of separate pay-per-token API billing; see "Brain: Claude Code CLI, not the API" below |
| Interface | Voice-first (wake word + STT + TTS), with text chat as fallback/dev interface | Matches the "JARVIS" experience; text mode used for testing without a mic |
| Platform | Cross-platform desktop app (Python + PySide6/Qt) | One codebase, native installers for Mac and Windows |
| Extensibility | "Skills" plugin system, exposed to Claude Code as MCP tools | Every capability (PDF report, ads reporting, Shopify sync, ...) is a self-contained skill; `jarvis/mcp_server.py` serves the whole registry as one MCP server |
| Workspace | Sandboxed folder (`~/Jarvis/workspace`) | Every file Jarvis creates/reads lives here — no unrestricted filesystem access |

## Brain: Claude Code CLI, not the API

JARVIS does not call the Anthropic Messages API directly. Instead,
`jarvis/core/llm.py` shells out to the `claude` binary in headless mode
(`claude -p ...`). When you've run `claude login` against a Claude Pro/Max
subscription (and have not set `ANTHROPIC_API_KEY`), that usage draws on
your subscription's included usage instead of metered API billing.

This has a real architectural consequence: **Claude Code runs its own
internal agentic tool-use loop**, so JARVIS doesn't implement one. A single
`claude -p` call can read a file, analyze it, generate a chart, and write a
PDF — all in one invocation — because Claude Code resolves the multi-step
tool use internally against the MCP tools we hand it. `Orchestrator` is
therefore a thin wrapper: build the command, run it, parse the JSON result.

Key flags used in every call (see `ClaudeCLIClient.build_args`):
- `--mcp-config` / `--strict-mcp-config` — points Claude Code at
  `jarvis/mcp_server.py` (spawned as a stdio subprocess) as the *only* MCP
  server, so it only has access to our own skills.
- `--allowedTools "mcp__jarvis__<skill>,..."` — explicitly whitelists just
  our skill tools.
- `--disallowedTools "Bash,Read,Write,Edit,Glob,Grep,WebFetch,..."` —
  explicitly denies Claude Code's built-in tools by name, so it can't touch
  anything outside the sandboxed workspace except through our own skills.
  **Gotcha (verified against Claude Code 2.1.198): don't use `--tools ""`
  for this instead** — despite the `--help` text implying it only affects
  the built-in tool set, it was observed to also suppress the MCP tool
  definitions from ever being shown to the model, silently breaking every
  skill (the model would just claim "I don't have that tool" or worse,
  hallucinate a plausible-looking answer without calling anything).
  `--disallowedTools` with explicit built-in names coexists correctly with
  `--mcp-config`.
- `--permission-mode dontAsk` — required for headless/scripted use: there's
  no human to click "allow." Note this only reliably blocks tools you've
  put in `--disallowedTools`; it is *not* by itself a safe default-deny for
  built-ins (verified: without an explicit deny list, Bash remained fully
  usable even though it wasn't in `--allowedTools`).
- `--system-prompt` — full replacement with JARVIS's persona (see
  `orchestrator.SYSTEM_PROMPT`), not Claude Code's default coding-assistant
  prompt.
- `--resume <session_id>` — the CLI's own on-disk session store, not our
  code, holds conversation context between turns; `session_id` comes back
  in the first call's JSON response and is persisted by `SessionMemory`.

## High-level architecture

```
                     ┌─────────────────────────┐
   mic  ──STT──▶     │                         │
                     │   Core Orchestrator     │──▶ `claude -p` (headless CLI call)
   text ────────────▶│  (session id + history) │      subscription-billed, runs its
                     │                         │◀──   own internal tool-use loop
   speaker ◀──TTS──  └─────────────────────────┘
                                 │ claude spawns, over MCP (stdio)
                                 ▼
                     ┌─────────────────────────┐
                     │   jarvis/mcp_server.py   │
                     │  (wraps the Skill        │
                     │   Registry as MCP tools) │
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
    llm.py             # ClaudeCLIClient: shells out to `claude -p` headlessly
    memory.py          # session id + transcript bookkeeping (JSON, on disk)
    orchestrator.py    # builds the system prompt, calls the CLI, returns the reply
  mcp_server.py         # MCP stdio server exposing the Skill Registry to Claude Code
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

- No API key is used or stored by default — auth is handled entirely by
  `claude login` (OAuth against your Claude account), managed by Claude
  Code itself, not by JARVIS's own code.
- Every headless `claude -p` call passes an explicit `--disallowedTools`
  deny-list for all built-ins plus an `--allowedTools` whitelist for our
  own MCP skills, so Claude Code has no Bash or unrestricted Read/Write
  access — verified live (a prompt asking it to `cat` a file outside the
  workspace was correctly refused).
- The filesystem skill can only read/write inside `~/Jarvis/workspace` —
  path traversal outside that folder is blocked.
- Voice wake-word detection runs fully locally/offline; only your actual
  spoken commands (after the wake word) are sent to the STT engine, and
  only the transcribed text is ever sent onward (to the `claude` CLI).
