import dataclasses

import jarvis.voice.wake_word as wake_word_module
from jarvis.voice.wake_word import DEFAULT_MODEL, WakeWordDetector


class _FakeModel:
    def __init__(self, wakeword_models):
        self.wakeword_models = wakeword_models

    def predict(self, chunk):
        return {}


def test_default_uses_pretrained_hey_jarvis_model(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    monkeypatch.setattr(
        wake_word_module, "settings", dataclasses.replace(wake_word_module.settings, wake_word_model="")
    )

    detector = WakeWordDetector()
    assert detector.model_name == DEFAULT_MODEL
    assert detector._model.wakeword_models == [DEFAULT_MODEL]


def test_explicit_model_path_overrides_default(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)

    detector = WakeWordDetector(model_path="/models/jarvis_wake_up.onnx")
    assert detector.model_name == "jarvis_wake_up"
    assert detector._model.wakeword_models == ["/models/jarvis_wake_up.onnx"]


def test_settings_wake_word_model_used_when_no_explicit_path(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    monkeypatch.setattr(
        wake_word_module,
        "settings",
        dataclasses.replace(wake_word_module.settings, wake_word_model="/models/custom.tflite"),
    )

    detector = WakeWordDetector()
    assert detector.model_name == "custom"
    assert detector._model.wakeword_models == ["/models/custom.tflite"]
