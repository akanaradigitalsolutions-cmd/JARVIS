# JARVIS

A personal AI assistant — like Iron Man's JARVIS — that runs on your Mac or
Windows machine. Powered by Claude, it's built to help with data analytics,
digital marketing (Google Ads, social ads), e-commerce for hospitality, web
development, and general digital work.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design and roadmap.

## Status

**Phase 1 (core + document/data skills) is done and tested.** Phase 1.5
(voice + desktop UI) is code-complete but needs testing on your machine —
this build environment has no microphone/speaker/display.

## Quick start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Add voice support (optional, bigger install):

```bash
pip install -e ".[voice]"
```

Add the desktop chat window (optional):

```bash
pip install -e ".[ui]"
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set `ANTHROPIC_API_KEY` to your Claude API key
(https://console.anthropic.com/).

### 3. Run

Text chat in your terminal (works everywhere, no setup needed beyond the
API key):

```bash
jarvis
```

Desktop chat window (requires `pip install -e ".[ui]"`):

```bash
jarvis --ui
```

Voice mode — say "Jarvis" to wake it, then speak your request (requires
`pip install -e ".[voice]"`):

```bash
jarvis --voice
```

## What it can already do (Phase 1)

Ask it in plain English, e.g.:

- "Summarize this CSV and make me a PDF report with charts" (put the CSV
  in `~/Jarvis/workspace` first, or tell it the full path)
- "Make a 5-slide presentation about our Q2 marketing results"
- "Read the file X and tell me what's in it"
- "List the files in my workspace"

All files Jarvis creates or reads live in `~/Jarvis/workspace` (configurable
via `JARVIS_WORKSPACE` in `.env`).

## Development

```bash
pip install -e ".[dev]"
pytest
```
