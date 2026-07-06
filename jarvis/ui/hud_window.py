"""Desktop shell for the JARVIS HUD: starts the local web server (see
jarvis/webui/server.py) in a background thread and displays it in a native
window via QWebEngineView — so `jarvis --ui` feels like a real app, not a
browser tab, while the actual HUD is just HTML/CSS/JS.

Also runs the same hands-free wake-word pipeline as `jarvis --voice` in a
background thread (VoiceBridgeThread): saying "Hey JARVIS" brings this
window to the front and drives the same chat UI, speaking the reply back.
If voice extras aren't installed, the HUD still runs fine — hands-free
just silently isn't available (a message is printed once, to stderr).

Run with `jarvis --ui`. Requires `pip install -e ".[ui]"` (add `[voice]"`
too for the hands-free wake word).
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from jarvis.webui.server import app as fastapi_app

# A fixed local-socket name a second `jarvis --ui` launch can connect to, so
# a global keyboard shortcut that just runs the app again (the natural way
# to wire one up on macOS) toggles the existing window to the front instead
# of piling up duplicate windows/servers every time it's pressed.
_SINGLE_INSTANCE_NAME = "jarvis-hud-single-instance"


def _activate_running_instance() -> bool:
    """If a JARVIS HUD is already running, tell it to come to the front and
    return True (the caller should then exit immediately instead of
    starting a second copy)."""
    sock = QLocalSocket()
    sock.connectToServer(_SINGLE_INSTANCE_NAME)
    connected = sock.waitForConnected(200)
    if connected:
        sock.write(b"show")
        sock.waitForBytesWritten(200)
        sock.disconnectFromServer()
    return connected


def _reveal_in_file_manager(path: Path) -> None:
    """Open the OS file browser with the downloaded file selected, so the
    user gets the same "there it is" feedback a real browser download bar
    would give — QWebEngineView itself has no such UI of its own."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", f"/select,{path}"], check=False)
        else:
            subprocess.run(["xdg-open", str(path.parent)], check=False)
    except OSError:
        pass


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


class VoiceBridgeThread(QThread):
    """Hands-free wake-word loop that drives the HUD instead of a terminal.

    Reuses the exact same wake-word/STT/TTS pipeline as `jarvis --voice`
    (jarvis/voice/loop.py), but instead of calling the orchestrator
    directly and printing to a terminal, it POSTs to this app's own local
    /api/chat (same server the window is already showing) and pushes the
    result into the page via Qt signals, so all the actual chat logic
    stays in one place (jarvis/webui/server.py).
    """

    wake_detected = Signal()
    thinking = Signal()
    speaking_started = Signal()
    speaking_finished = Signal()
    exchange_ready = Signal(str, str, str)  # user_text, reply_text, files_json
    voice_error = Signal(str)
    setup_failed = Signal(str)

    def __init__(self, port: int) -> None:
        super().__init__()
        self.port = port
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            import numpy as np
            import requests
            import sounddevice as sd

            from jarvis.voice.loop import (
                CHUNK_SAMPLES,
                SAMPLE_RATE,
                _record_command,
            )
            from jarvis.voice.stt import transcribe
            from jarvis.voice.stt import warmup as warmup_stt
            from jarvis.voice.tts import speak, speak_wake_acknowledgement
            from jarvis.voice.wake_word import WakeWordDetector
        except ImportError as exc:
            self.setup_failed.emit(
                "Voice extras aren't installed, hands-free wake word is off. "
                f"Run: pip install -e '.[voice]' (missing: {exc.name})"
            )
            return
        except OSError as exc:
            # sounddevice raises OSError (not ImportError) at import time if
            # the native PortAudio library isn't available on this machine.
            self.setup_failed.emit(f"Voice extras couldn't load, hands-free wake word is off: {exc}")
            return

        try:
            detector = WakeWordDetector()
            warmup_stt()
            stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK_SAMPLES)
            stream.start()
        except Exception as exc:  # noqa: BLE001 - report any startup failure, keep the HUD itself usable
            self.setup_failed.emit(f"Couldn't start hands-free voice: {exc}")
            return

        try:
            while not self._stop.is_set():
                chunk, _overflowed = stream.read(CHUNK_SAMPLES)
                int16_chunk = (chunk.flatten() * 32767).astype(np.int16)

                if not detector.process_chunk(int16_chunk):
                    continue

                self.wake_detected.emit()
                self.speaking_started.emit()
                speak_wake_acknowledgement()
                self.speaking_finished.emit()
                audio = _record_command(stream)
                text = transcribe(audio)
                if not text:
                    continue

                self.thinking.emit()
                try:
                    resp = requests.post(
                        f"http://127.0.0.1:{self.port}/api/chat", json={"message": text}, timeout=180
                    )
                    data = resp.json()
                except Exception as exc:  # noqa: BLE001 - network hiccup shouldn't kill the loop
                    self.voice_error.emit(str(exc))
                    continue

                if resp.status_code != 200:
                    self.voice_error.emit(data.get("detail", "Something went wrong."))
                    continue

                reply = data.get("reply", "")
                self.exchange_ready.emit(text, reply, json.dumps(data.get("files", [])))
                # The HUD used to flip back to "online" here even though speak()
                # below hadn't run yet, so it visually looked idle while JARVIS
                # was still actually talking. speaking_started/finished bracket
                # the real speaking duration so the HUD state matches reality.
                self.speaking_started.emit()
                if reply:
                    speak(reply)
                self.speaking_finished.emit()
        finally:
            stream.stop()
            stream.close()


class HudWindow(QMainWindow):
    def __init__(self, port: int) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.resize(860, 780)
        self.view = QWebEngineView()
        self.view.load(QUrl(f"http://127.0.0.1:{port}/"))
        self.setCentralWidget(self.view)
        self.view.page().profile().downloadRequested.connect(self._on_download_requested)

        self.voice_thread = VoiceBridgeThread(port)
        self.voice_thread.wake_detected.connect(self._on_wake_detected)
        self.voice_thread.thinking.connect(self._on_thinking)
        self.voice_thread.speaking_started.connect(self._on_speaking_started)
        self.voice_thread.speaking_finished.connect(self._on_speaking_finished)
        self.voice_thread.exchange_ready.connect(self._on_exchange_ready)
        self.voice_thread.voice_error.connect(self._on_voice_error)
        self.voice_thread.setup_failed.connect(self._on_voice_setup_failed)
        self.voice_thread.start()

        # Listen for a second `jarvis --ui` launch (e.g. from a keyboard
        # shortcut) telling us to come to the front, instead of it starting
        # a whole second instance — see _activate_running_instance().
        QLocalServer.removeServer(_SINGLE_INSTANCE_NAME)
        self._ipc_server = QLocalServer(self)
        self._ipc_server.listen(_SINGLE_INSTANCE_NAME)
        self._ipc_server.newConnection.connect(self._on_ipc_connection)

    def _on_ipc_connection(self) -> None:
        conn = self._ipc_server.nextPendingConnection()
        if conn is None:
            return
        conn.readyRead.connect(lambda: self._handle_ipc_message(conn))

    def _handle_ipc_message(self, conn) -> None:
        if bytes(conn.readAll()).strip() == b"show":
            self.bring_to_front()
        conn.disconnectFromServer()

    def bring_to_front(self) -> None:
        # Best-effort: macOS may still keep another app focused (e.g. a
        # fullscreen app in a different Space, or Focus/Do Not Disturb
        # mode) — that's an OS-level restriction, not something an app can
        # force past.
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_download_requested(self, download: QWebEngineDownloadRequest) -> None:
        """QWebEngineView has no built-in download UI at all — clicking a
        generated file's card in the HUD would otherwise silently do
        nothing. Auto-save to ~/Downloads and reveal it, matching the
        experience of clicking a file card in a real Claude chat window.
        """
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        download.setDownloadDirectory(str(downloads_dir))
        download.setDownloadFileName(download.suggestedFileName())

        def _on_state_changed(state: QWebEngineDownloadRequest.DownloadState) -> None:
            if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                _reveal_in_file_manager(downloads_dir / download.downloadFileName())

        download.stateChanged.connect(_on_state_changed)
        download.accept()

    def shutdown_voice_thread(self) -> None:
        """Stop the background voice thread before Qt/Python teardown.

        A blocked network call (e.g. a slow /api/chat request) can keep the
        thread alive well past a short grace period. Destroying a QThread
        object while its underlying OS thread is still running aborts the
        whole process (Qt's QThread destructor calls qFatal), so if it
        doesn't stop in time we forcibly terminate it and wait for real.
        """
        self.voice_thread.stop()
        if not self.voice_thread.wait(2000):
            self.voice_thread.terminate()
            self.voice_thread.wait()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override naming convention
        self.shutdown_voice_thread()
        super().closeEvent(event)

    def _run_js(self, script: str) -> None:
        self.view.page().runJavaScript(script)

    def _on_wake_detected(self) -> None:
        self.bring_to_front()
        self._run_js("window.jarvisVoiceBridge && window.jarvisVoiceBridge.onWake()")

    def _on_thinking(self) -> None:
        self._run_js("window.jarvisVoiceBridge && window.jarvisVoiceBridge.onThinking()")

    def _on_speaking_started(self) -> None:
        self._run_js("window.jarvisVoiceBridge && window.jarvisVoiceBridge.onSpeakingStart()")

    def _on_speaking_finished(self) -> None:
        self._run_js("window.jarvisVoiceBridge && window.jarvisVoiceBridge.onSpeakingEnd()")

    def _on_exchange_ready(self, user_text: str, reply_text: str, files_json: str) -> None:
        script = (
            "window.jarvisVoiceBridge && window.jarvisVoiceBridge.onExchange("
            f"{json.dumps(user_text)}, {json.dumps(reply_text)}, {json.dumps(files_json)})"
        )
        self._run_js(script)

    def _on_voice_error(self, message: str) -> None:
        self._run_js(f"window.jarvisVoiceBridge && window.jarvisVoiceBridge.onError({json.dumps(message)})")

    def _on_voice_setup_failed(self, message: str) -> None:
        print(f"(voice) {message}", file=sys.stderr)


def run() -> None:
    # QLocalSocket needs a QCoreApplication instance to work at all, so this
    # has to exist before the single-instance check — cheap, doesn't start
    # the event loop yet.
    app = QApplication(sys.argv)

    if _activate_running_instance():
        print("JARVIS is already running — bringing it to the front.")
        return

    port = _free_port()
    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(port):
        print("JARVIS's local server didn't start in time.", file=sys.stderr)
        raise SystemExit(1)

    window = HudWindow(port)
    app.aboutToQuit.connect(window.shutdown_voice_thread)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
