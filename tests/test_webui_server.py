import io

from fastapi.testclient import TestClient

import jarvis.webui.server as server_module
from jarvis.webui.server import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_index_serves_hud_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "JARVIS" in res.text


def test_upload_then_list_then_download():
    res = client.post("/api/upload", files={"file": ("notes.txt", io.BytesIO(b"hello hud"), "text/plain")})
    assert res.status_code == 200
    assert res.json() == {"name": "notes.txt", "size_bytes": 9}

    res = client.get("/api/files")
    names = [f["name"] for f in res.json()["files"]]
    assert "notes.txt" in names

    res = client.get("/api/download/notes.txt")
    assert res.status_code == 200
    assert res.content == b"hello hud"


def test_download_rejects_path_traversal():
    res = client.get("/api/download/../../etc/passwd")
    assert res.status_code in (400, 404)


def test_download_missing_file_is_404():
    res = client.get("/api/download/does-not-exist.txt")
    assert res.status_code == 404


def test_chat_empty_message_is_rejected():
    res = client.post("/api/chat", json={"message": "  "})
    assert res.status_code == 400


class _FakeMemory:
    session_id = "fake-session-123"


class _FakeOrchestrator:
    def __init__(self):
        self.memory = _FakeMemory()
        self.last_message = None

    def handle_message(self, text):
        self.last_message = text
        return f"echo: {text}"


def test_chat_uses_orchestrator_and_reports_new_files(monkeypatch):
    fake = _FakeOrchestrator()
    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: fake)

    res = client.post("/api/chat", json={"message": "hello jarvis"})
    assert res.status_code == 200
    data = res.json()
    assert data["reply"] == "echo: hello jarvis"
    assert data["session_id"] == "fake-session-123"
    assert fake.last_message == "hello jarvis"


def test_chat_surfaces_orchestrator_errors_as_500(monkeypatch):
    class _BrokenOrchestrator(_FakeOrchestrator):
        def handle_message(self, text):
            raise RuntimeError("claude CLI blew up")

    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: _BrokenOrchestrator())

    res = client.post("/api/chat", json={"message": "hello"})
    assert res.status_code == 500
    assert "claude CLI blew up" in res.json()["detail"]
