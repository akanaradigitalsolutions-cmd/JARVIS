"""Desktop chat window (PySide6): a chat UI wired to the same orchestrator
as the CLI, with a push-to-talk mic button for voice input.

Run with `jarvis --ui`. Requires `pip install -e ".[ui]"`. For the mic
button you'll also need `pip install -e ".[voice]"` (STT only — this
window doesn't use the always-on wake word, you just click the mic).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jarvis.core.llm import MissingApiKeyError
from jarvis.core.memory import SessionMemory
from jarvis.core.orchestrator import Orchestrator

VOICE_CAPTURE_SECONDS = 6
VOICE_SAMPLE_RATE = 16000


class ChatWorker(QThread):
    reply_ready = Signal(str)
    error = Signal(str)

    def __init__(self, orchestrator: Orchestrator, text: str) -> None:
        super().__init__()
        self._orchestrator = orchestrator
        self._text = text

    def run(self) -> None:
        try:
            reply = self._orchestrator.handle_message(self._text)
            self.reply_ready.emit(reply)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.error.emit(str(exc))


class VoiceCaptureWorker(QThread):
    """Push-to-talk: records a few seconds of audio and transcribes it.

    Voice deps are imported lazily so the UI runs fine without them
    installed — only clicking the mic button requires them.
    """

    transcribed = Signal(str)
    error = Signal(str)

    def run(self) -> None:
        try:
            import sounddevice as sd

            from jarvis.voice.stt import transcribe

            audio = sd.rec(
                int(VOICE_CAPTURE_SECONDS * VOICE_SAMPLE_RATE),
                samplerate=VOICE_SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            text = transcribe(audio.flatten())
            self.transcribed.emit(text)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.error.emit(str(exc))


class ChatWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.resize(720, 640)

        self.orchestrator: Orchestrator | None = None
        setup_error: str | None = None
        try:
            self.orchestrator = Orchestrator(memory=SessionMemory())
        except MissingApiKeyError as exc:
            setup_error = str(exc)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        layout.addWidget(self.transcript)

        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask JARVIS anything...")
        self.input_field.returnPressed.connect(self.send_message)
        input_row.addWidget(self.input_field)

        self.mic_button = QPushButton("\U0001F3A4")
        self.mic_button.setFixedWidth(40)
        self.mic_button.setToolTip("Push to talk")
        self.mic_button.clicked.connect(self.start_voice_capture)
        input_row.addWidget(self.mic_button)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_row.addWidget(self.send_button)

        layout.addLayout(input_row)

        self._chat_worker: ChatWorker | None = None
        self._voice_worker: VoiceCaptureWorker | None = None

        if setup_error:
            self._append("jarvis", f"Setup needed: {setup_error}")
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)
            self.mic_button.setEnabled(False)
        else:
            self._append("jarvis", "Hello. How can I help?")

    def _append(self, speaker: str, text: str) -> None:
        label = "You" if speaker == "you" else "JARVIS"
        self.transcript.append(f"<b>{label}:</b> {text}\n")

    def _set_busy(self, busy: bool) -> None:
        self.input_field.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.mic_button.setEnabled(not busy)

    def send_message(self) -> None:
        text = self.input_field.text().strip()
        if not text or self.orchestrator is None:
            return
        self.input_field.clear()
        self._append("you", text)
        self._set_busy(True)

        self._chat_worker = ChatWorker(self.orchestrator, text)
        self._chat_worker.reply_ready.connect(self._on_reply)
        self._chat_worker.error.connect(self._on_error)
        self._chat_worker.start()

    def _on_reply(self, reply: str) -> None:
        self._append("jarvis", reply or "(no response)")
        self._set_busy(False)

    def _on_error(self, message: str) -> None:
        self._append("jarvis", f"Error: {message}")
        self._set_busy(False)

    def start_voice_capture(self) -> None:
        self._set_busy(True)
        self._append("jarvis", f"(listening for {VOICE_CAPTURE_SECONDS} seconds...)")

        self._voice_worker = VoiceCaptureWorker()
        self._voice_worker.transcribed.connect(self._on_transcribed)
        self._voice_worker.error.connect(self._on_voice_error)
        self._voice_worker.start()

    def _on_transcribed(self, text: str) -> None:
        self._set_busy(False)
        if not text:
            self._append("jarvis", "Sorry, I didn't catch that.")
            return
        self.input_field.setText(text)
        self.send_message()

    def _on_voice_error(self, message: str) -> None:
        self._set_busy(False)
        self._append(
            "jarvis",
            f"Voice input isn't available: {message}\n"
            "Make sure you've installed the voice extras: pip install -e '.[voice]'",
        )


def run() -> None:
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
