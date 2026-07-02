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
    wake_word.py         # "Hey JARVIS" wake word detection (openWakeWord), swappable for a custom-trained model
    loop.py              # ties mic -> STT -> orchestrator -> TTS -> speaker
  webui/
    server.py             # FastAPI app: /api/chat, /api/upload, /api/download, /api/transcribe
    static/                # the HUD itself: index.html, style.css, app.js (no build step, no deps)
  ui/
    hud_window.py         # PySide6 QWebEngineView shell + VoiceBridgeThread (hands-free wake word -> HUD)
  cli.py                 # terminal chat client (always works, no audio needed)
  main.py                 # entry point: `jarvis`, `jarvis --voice`, `jarvis --ui`
```

## Custom wake word

Voice mode listens for **"Hey JARVIS"** by default — openWakeWord's free,
pretrained model, trained by its maintainers on ~30,000 hours of negative
audio. That's not something worth trying to beat with a homemade model.

If you want an exact custom phrase instead (e.g. "JARVIS wake up"),
training one needs a GPU and several GB of dataset downloads — genuinely
not feasible in a plain CPU sandbox. The practical way to do it:

1. Open the official openWakeWord training notebook in Google Colab (free
   GPU): **[`automatic_model_training.ipynb`](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)**
   (from the [openWakeWord repo](https://github.com/dscripka/openWakeWord)).
2. In Colab: **Runtime → Change runtime type → GPU** (T4 is fine, free tier).
3. In the notebook's config cell, set your target phrase, e.g.:
   ```yaml
   target_phrase: ["jarvis wake up"]
   model_name: "jarvis_wake_up"
   ```
4. Run all cells (~20-30 min on the free GPU tier). It generates synthetic
   TTS training samples for your phrase, trains a small classifier against
   openWakeWord's precomputed negative-audio features, and exports a
   `jarvis_wake_up.onnx` (or `.tflite`) file.
5. Download that model file to your Mac, e.g. into `~/Jarvis/models/`.
6. Point JARVIS at it — in `.env`:
   ```
   JARVIS_WAKE_WORD_MODEL=/Users/you/Jarvis/models/jarvis_wake_up.onnx
   JARVIS_WAKE_WORD=jarvis wake up
   ```
   No code changes needed — `jarvis/voice/wake_word.py` picks up a custom
   model path automatically and falls back to "Hey JARVIS" if it's unset.

Expect to iterate: a first pass often has too many false positives/negatives
until you retrain with a larger sample count or adjust the detection
threshold (`WakeWordDetector(threshold=...)`). Since I can't hear your mic
from here, this loop — you test, tell me what's misfiring, I adjust the
threshold or help tune the notebook config — has to happen with you in
the loop.

## Roadmap (phased delivery)

- **Phase 1 — Core + first real skills (done)**
  Orchestrator, skill system, filesystem skill, document generation
  (PDF/PPTX/Excel), data analysis skill, CLI chat. Fully working and
  testable without any special hardware.

- **Phase 1.5 — Voice + Desktop HUD (done, verified on real hardware)**
  STT/TTS/wake-word modules for hands-free voice mode (`jarvis --voice`) —
  confirmed working end-to-end on a real Mac: wake-word detection,
  transcription, and a spoken reply. The desktop HUD (`jarvis --ui`) is
  **done and verified**: a FastAPI backend (`jarvis/webui/server.py`)
  wraps the Orchestrator with a small JSON API (chat, file upload/download,
  browser-mic transcription), and a dependency-free HTML/CSS/JS frontend
  (`jarvis/webui/static/`) renders an animated arc-reactor-style HUD with a
  Claude-like chat box (drag/drop attachments, generated files shown as
  downloadable cards, push-to-talk mic using raw Web Audio API PCM capture
  — no browser codec issues). It's shown inside a native window via
  PySide6's `QWebEngineView` (`jarvis/ui/hud_window.py`) rather than a
  browser tab. Verified with a live browser-engine-driven test: typing a
  request, submitting the real form, and confirming the PDF/chart file
  cards rendered correctly from an actual multi-tool Claude Code CLI call.

  The HUD also fuses in the hands-free pipeline: `HudWindow` runs a
  `VoiceBridgeThread` in the background (same wake-word/STT/TTS pipeline as
  `jarvis --voice`) that, on "Hey JARVIS", brings the window to the front
  and pushes the exchange into the same chat log via a small JS bridge
  (`window.jarvisVoiceBridge`, driven from Python via
  `QWebEngineView.page().runJavaScript()`), rather than duplicating the
  chat UI in Qt widgets. It POSTs to the HUD's own local `/api/chat`
  (the same endpoint the browser-side JS uses) rather than calling the
  orchestrator directly, so there's exactly one code path for "handle a
  chat message," used by typing, the push-to-talk button, and hands-free
  wake word alike. Verified with a live headless test driving the actual
  Qt signal → JS injection → DOM-render path end-to-end; the audio
  hardware side (does saying "Hey JARVIS" really trigger it) inherits the
  same verification as `jarvis --voice` above, since it's the same
  underlying wake-word code.
  Note: bringing the window to the front on wake is best-effort —
  macOS can still keep another app focused (fullscreen app in a different
  Space, Focus/Do Not Disturb mode, etc.); that's an OS-level restriction
  no app can override.

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
