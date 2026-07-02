"""Desktop shell for the JARVIS HUD: starts the local web server (see
jarvis/webui/server.py) in a background thread and displays it in a native
window via QWebEngineView — so `jarvis --ui` feels like a real app, not a
browser tab, while the actual HUD is just HTML/CSS/JS.

Run with `jarvis --ui`. Requires `pip install -e ".[ui]"`.
"""

from __future__ import annotations

import socket
import sys
import threading
import time

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from jarvis.webui.server import app as fastapi_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> None:
    import uvicorn

    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")


def _wait_for_server(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


class HudWindow(QMainWindow):
    def __init__(self, port: int) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.resize(860, 780)
        self.view = QWebEngineView()
        self.view.load(QUrl(f"http://127.0.0.1:{port}/"))
        self.setCentralWidget(self.view)


def run() -> None:
    port = _free_port()
    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(port):
        print("JARVIS's local server didn't start in time.", file=sys.stderr)
        raise SystemExit(1)

    app = QApplication(sys.argv)
    window = HudWindow(port)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
