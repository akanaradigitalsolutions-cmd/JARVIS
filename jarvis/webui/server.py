"""Local web server backing the JARVIS HUD: a small JSON API in front of
the same Orchestrator the CLI and voice loop use, plus the static HUD
frontend (jarvis/webui/static/). Runs entirely on localhost — nothing here
is exposed to the network.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jarvis.core.config import settings
from jarvis.core.llm import ClaudeCLINotAvailableError
from jarvis.core.memory import SessionMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.skills.filesystem import PathOutsideWorkspaceError, resolve_in_workspace

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="JARVIS")

_orchestrator: Orchestrator | None = None
_orchestrator_error: str | None = None
_lock = threading.Lock()


def _get_orchestrator() -> Orchestrator:
    global _orchestrator, _orchestrator_error
    if _orchestrator is None and _orchestrator_error is None:
        try:
            _orchestrator = Orchestrator(memory=SessionMemory())
        except ClaudeCLINotAvailableError as exc:
            _orchestrator_error = str(exc)
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail=_orchestrator_error)
    return _orchestrator


def _snapshot_workspace() -> dict[str, float]:
    if not settings.workspace.exists():
        return {}
    return {
        str(p.relative_to(settings.workspace)): p.stat().st_mtime
        for p in settings.workspace.rglob("*")
        if p.is_file()
    }


def _file_info(relative_path: str) -> dict[str, Any]:
    path = settings.workspace / relative_path
    return {"name": relative_path, "size_bytes": path.stat().st_size}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "workspace": str(settings.workspace)}


@app.post("/api/chat")
def chat(payload: dict) -> dict:
    message = (payload or {}).get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    orchestrator = _get_orchestrator()

    with _lock:
        before = _snapshot_workspace()
        start = time.monotonic()
        try:
            reply = orchestrator.handle_message(message)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        duration_s = time.monotonic() - start
        after = _snapshot_workspace()

    new_or_changed = sorted(k for k in after if k not in before or after[k] != before[k])
    return {
        "reply": reply,
        "session_id": orchestrator.memory.session_id,
        "duration_s": round(duration_s, 2),
        "files": [_file_info(p) for p in new_or_changed],
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    try:
        dest = resolve_in_workspace(file.filename)
    except PathOutsideWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    return {"name": file.filename, "size_bytes": len(content)}


@app.get("/api/files")
def list_files() -> dict:
    return {"files": [_file_info(p) for p in sorted(_snapshot_workspace())]}


@app.get("/api/download/{path:path}")
def download(path: str) -> FileResponse:
    try:
        resolved = resolve_in_workspace(path)
    except PathOutsideWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"'{path}' not found")
    return FileResponse(resolved, filename=resolved.name)


@app.post("/api/transcribe")
async def transcribe_audio(request: Request) -> dict:
    """Accepts a raw application/octet-stream body: little-endian float32
    PCM samples, mono, 16kHz — captured directly via the Web Audio API in
    the browser (see static/app.js). No container/codec decoding needed.
    """
    try:
        import numpy as np

        from jarvis.voice.stt import transcribe
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Voice extras aren't installed. Run: pip install -e '.[voice]' (missing: {exc.name})",
        ) from exc

    body = await request.body()
    audio = np.frombuffer(body, dtype="<f4").astype("float32")
    text = transcribe(audio)
    return {"text": text}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def run_server(host: str = "127.0.0.1", port: int = 8756) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    # `python -m jarvis.webui.server` — run the server standalone in a
    # regular browser tab, useful for developing/testing the HUD without
    # the PySide6 desktop shell.
    run_server()
