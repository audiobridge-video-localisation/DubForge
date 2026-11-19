import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from dubforge_pipeline.providers.edge_tts import EdgeTTSProvider, _resolve_voice

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _write_fake_speech_mp3(path: Path, seconds: float = 1.0) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-codec:a",
            "libmp3lame",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


class FakeCommunicate:
    fail_with: Exception | None = None
    save_calls = 0
    rates: list[str] = []

    def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
        self.text = text
        self.voice = voice
        self.rate = rate

    async def save(self, path: str) -> None:
        FakeCommunicate.save_calls += 1
        FakeCommunicate.rates.append(self.rate)
        if FakeCommunicate.fail_with is not None:
            raise FakeCommunicate.fail_with
        # a faster rate makes the fake take shorter, like the real service
        _write_fake_speech_mp3(Path(path), seconds=1.0 / (1 + int(self.rate.rstrip("%")) / 100))


@pytest.fixture(autouse=True)
def _reset_fake_communicate() -> None:
    FakeCommunicate.fail_with = None
    FakeCommunicate.save_calls = 0
    FakeCommunicate.rates = []


@pytest.fixture(autouse=True)
def _clear_tts_rate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TTS_RATE", raising=False)


@pytest.fixture
def mock_edge_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("edge_tts")
    fake_module.Communicate = FakeCommunicate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "edge_tts", fake_module)


def test_resolve_voice_language_mapping() -> None:
    assert _resolve_voice("hi") == "hi-IN-SwaraNeural"
    assert _resolve_voice("bn") == "bn-IN-TanishaaNeural"


def test_resolve_voice_override_with_exact_voice_name() -> None:
    assert _resolve_voice("hi-IN-SwaraNeural") == "hi-IN-SwaraNeural"


def test_resolve_voice_unsupported_raises_value_error() -> None:
    with pytest.raises(ValueError, match="fr"):
        _resolve_voice("fr")


def test_resolve_voice_picks_a_different_voice_per_speaker_index() -> None:
    first = _resolve_voice("hi", speaker_index=0)
    second = _resolve_voice("hi", speaker_index=1)
    assert first == "hi-IN-SwaraNeural"
    assert second != first


def test_resolve_voice_wraps_around_the_pool_for_extra_speakers() -> None:
    # More distinct speakers than voices in the pool: wrap back to voice 0, not an error.
    assert _resolve_voice("hi", speaker_index=2) == _resolve_voice("hi", speaker_index=0)


def test_resolve_voice_without_speaker_index_keeps_the_default_voice() -> None:
    # Callers that only pass a language (no diarization info, e.g. tests/manual overrides)
    # keep getting the same voice as before this pool existed.
    assert _resolve_voice("hi") == "hi-IN-SwaraNeural"
    assert _resolve_voice("hi", speaker_index=None) == "hi-IN-SwaraNeural"


def test_resolve_voice_exact_override_ignores_speaker_index() -> None:
    assert _resolve_voice("hi-IN-SwaraNeural", speaker_index=1) == "hi-IN-SwaraNeural"


def test_resolve_voice_gender_steers_the_first_speaker() -> None:
    # Default order (no preference) puts the female voice first.
    assert _resolve_voice("hi", speaker_index=0) == "hi-IN-SwaraNeural"
    # Asking for male moves it to speaker_index=0 instead.
    assert _resolve_voice("hi", speaker_index=0, voice_gender="male") == "hi-IN-MadhurNeural"
    assert _resolve_voice("hi", speaker_index=0, voice_gender="female") == "hi-IN-SwaraNeural"


def test_resolve_voice_gender_still_distinguishes_other_speakers() -> None:
    # A second speaker still gets a different voice from the first, whichever gender
    # was requested for the first - distinctness between speakers isn't lost.
    first = _resolve_voice("hi", speaker_index=0, voice_gender="male")
    second = _resolve_voice("hi", speaker_index=1, voice_gender="male")
    assert first != second


def test_resolve_voice_gender_ignored_without_speaker_index() -> None:
    # No diarization info at all: voice_gender alone still works (index defaults to 0).
    assert _resolve_voice("hi", voice_gender="male") == "hi-IN-MadhurNeural"


def test_synthesize_produces_wav(tmp_path: Path, mock_edge_tts: None) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi")

    assert Path(result.audio_path).exists()
    assert Path(result.audio_path).stat().st_size > 0
    assert result.actual_duration_ms > 0
    assert FakeCommunicate.save_calls == 1


def test_synthesize_keeps_a_take_that_is_not_too_long(tmp_path: Path, mock_edge_tts: None) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi", target_duration_ms=999_999)

    assert FakeCommunicate.rates == ["+0%"]
    assert result.speech_rate == 1.0
    assert result.actual_duration_ms != 999_999  # the real audio length, never the target


def test_synthesize_speaks_faster_when_the_take_is_too_long(
    tmp_path: Path, mock_edge_tts: None
) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi", target_duration_ms=500)

    assert FakeCommunicate.rates == ["+0%", "+25%"]  # capped at MAX_SPEEDUP
    assert result.speech_rate == pytest.approx(1.25)
    assert result.actual_duration_ms < 900  # about 1000 / 1.25


def test_synthesize_starts_at_tts_rate_and_speeds_up_on_top_of_it(
    tmp_path: Path, mock_edge_tts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TTS_RATE", "+20%")
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi", target_duration_ms=500)

    # 1.2x is the voice's normal pace; the speed-up for the long line multiplies it
    assert FakeCommunicate.rates == ["+20%", "+50%"]
    assert result.speech_rate == pytest.approx(1.25)  # measured from TTS_RATE, not natural


def test_synthesize_empty_text_does_not_raise(tmp_path: Path, mock_edge_tts: None) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("   ", "hi")

    assert Path(result.audio_path).exists()


def test_synthesize_unsupported_language_raises_value_error(
    tmp_path: Path, mock_edge_tts: None
) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="fr"):
        provider.synthesize("Hello.", "fr")
    assert FakeCommunicate.save_calls == 0


def test_rate_defaults_to_unchanged_speed(tmp_path: Path, mock_edge_tts: None) -> None:
    EdgeTTSProvider(output_dir=str(tmp_path)).synthesize("Hello there.", "hi")

    assert FakeCommunicate.rates[-1] == "+0%"


@pytest.mark.parametrize("rate", ["+30%", "-10%", "+0%"])
def test_rate_from_env_is_passed_to_communicate(
    tmp_path: Path, mock_edge_tts: None, monkeypatch: pytest.MonkeyPatch, rate: str
) -> None:
    monkeypatch.setenv("TTS_RATE", rate)

    EdgeTTSProvider(output_dir=str(tmp_path)).synthesize("Hello there.", "hi")

    assert FakeCommunicate.rates[-1] == rate


def test_rate_argument_overrides_env(
    tmp_path: Path, mock_edge_tts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TTS_RATE", "+30%")

    EdgeTTSProvider(output_dir=str(tmp_path), rate="+10%").synthesize("Hello there.", "hi")

    assert FakeCommunicate.rates[-1] == "+10%"


@pytest.mark.parametrize("rate", ["30%", "+30", "fast", "+3.5%", "+%", "++30%", " +30%", "+30% "])
def test_invalid_rate_env_is_rejected(monkeypatch: pytest.MonkeyPatch, rate: str) -> None:
    monkeypatch.setenv("TTS_RATE", rate)

    with pytest.raises(ValueError, match="TTS_RATE"):
        EdgeTTSProvider()


def test_synthesize_network_failure_raises_runtime_error(
    tmp_path: Path, mock_edge_tts: None
) -> None:
    FakeCommunicate.fail_with = ConnectionError("no network")
    provider = EdgeTTSProvider(output_dir=str(tmp_path))

    with pytest.raises(RuntimeError, match="edge-tts request failed"):
        provider.synthesize("Hello.", "hi")
