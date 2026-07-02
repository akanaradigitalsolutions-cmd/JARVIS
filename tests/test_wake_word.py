import dataclasses

import jarvis.voice.wake_word as wake_word_module
from jarvis.voice.wake_word import DEFAULT_MODEL, DEFAULT_MODEL_KEY, WakeWordDetector


class _FakeModel:
    def __init__(self, wakeword_models, inference_framework=None):
        self.wakeword_models = wakeword_models
        self.inference_framework = inference_framework

    def predict(self, chunk):
        return {}


def _no_download_calls_tracker(monkeypatch):
    calls = []
    monkeypatch.setattr(wake_word_module, "download_models", lambda names: calls.append(names))
    return calls


def test_default_uses_pretrained_hey_jarvis_model(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    download_calls = _no_download_calls_tracker(monkeypatch)
    monkeypatch.setattr(
        wake_word_module, "settings", dataclasses.replace(wake_word_module.settings, wake_word_model="")
    )

    detector = WakeWordDetector()
    assert detector.model_name == DEFAULT_MODEL
    assert detector._model.wakeword_models == [DEFAULT_MODEL]
    assert detector._model.inference_framework == "onnx"
    assert download_calls == [[DEFAULT_MODEL_KEY]]


def test_explicit_model_path_overrides_default_and_skips_download(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    download_calls = _no_download_calls_tracker(monkeypatch)

    detector = WakeWordDetector(model_path="/models/jarvis_wake_up.onnx")
    assert detector.model_name == "jarvis_wake_up"
    assert detector._model.wakeword_models == ["/models/jarvis_wake_up.onnx"]
    assert download_calls == []  # custom models are used as-is, never fetched


def test_settings_wake_word_model_used_when_no_explicit_path(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    download_calls = _no_download_calls_tracker(monkeypatch)
    monkeypatch.setattr(
        wake_word_module,
        "settings",
        dataclasses.replace(wake_word_module.settings, wake_word_model="/models/custom.tflite"),
    )

    detector = WakeWordDetector()
    assert detector.model_name == "custom"
    assert detector._model.wakeword_models == ["/models/custom.tflite"]
    assert download_calls == []


def test_threshold_defaults_to_settings_value(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    _no_download_calls_tracker(monkeypatch)
    monkeypatch.setattr(
        wake_word_module, "settings", dataclasses.replace(wake_word_module.settings, wake_word_threshold=0.22)
    )

    detector = WakeWordDetector()
    assert detector.threshold == 0.22


def test_explicit_threshold_overrides_settings(monkeypatch):
    monkeypatch.setattr(wake_word_module, "Model", _FakeModel)
    _no_download_calls_tracker(monkeypatch)
    monkeypatch.setattr(
        wake_word_module, "settings", dataclasses.replace(wake_word_module.settings, wake_word_threshold=0.22)
    )

    detector = WakeWordDetector(threshold=0.9)
    assert detector.threshold == 0.9
