from dataclasses import dataclass

from jarvis.voice.tts import _pick_voice


@dataclass
class _FakeVoice:
    id: str
    name: str


class _FakeEngine:
    def __init__(self, voices):
        self._voices = voices
        self.selected_voice_id = None

    def getProperty(self, name):
        assert name == "voices"
        return self._voices

    def setProperty(self, name, value):
        assert name == "voice"
        self.selected_voice_id = value


_SAMPLE_VOICES = [
    _FakeVoice(id="com.apple.voice.compact.en-US.Samantha", name="Samantha"),
    _FakeVoice(id="com.apple.voice.compact.en-GB.Daniel", name="Daniel"),
    _FakeVoice(id="com.apple.voice.compact.fr-FR.Thomas", name="Thomas"),
]


def test_picks_daniel_over_default_when_no_override():
    engine = _FakeEngine(_SAMPLE_VOICES)
    _pick_voice(engine)
    assert engine.selected_voice_id == "com.apple.voice.compact.en-GB.Daniel"


def test_falls_back_to_none_selected_when_no_match():
    engine = _FakeEngine([_SAMPLE_VOICES[0], _SAMPLE_VOICES[2]])  # no British voice
    _pick_voice(engine)
    assert engine.selected_voice_id is None


def test_espeak_style_great_britain_voice_is_matched():
    voices = [
        _FakeVoice(id="gmw/en-us", name="English (America)"),
        _FakeVoice(id="gmw/en", name="English (Great Britain)"),
    ]
    engine = _FakeEngine(voices)
    _pick_voice(engine)
    assert engine.selected_voice_id == "gmw/en"


def test_empty_voice_list_does_not_crash():
    engine = _FakeEngine([])
    _pick_voice(engine)  # should not raise
    assert engine.selected_voice_id is None
