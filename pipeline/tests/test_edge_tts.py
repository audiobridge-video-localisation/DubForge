import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from dubforge_pipeline.providers.edge_tts import EdgeTTSProvider, _resolve_voice

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _write_fake_speech_mp3(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
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

    def __init__(self, text: str, voice: str) -> None:
        self.text = text
        self.voice = voice

    async def save(self, path: str) -> None:
        FakeCommunicate.save_calls += 1
        if FakeCommunicate.fail_with is not None:
            raise FakeCommunicate.fail_with
        _write_fake_speech_mp3(Path(path))


@pytest.fixture(autouse=True)
def _reset_fake_communicate() -> None:
    FakeCommunicate.fail_with = None
    FakeCommunicate.save_calls = 0


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


def test_synthesize_produces_wav(tmp_path: Path, mock_edge_tts: None) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi")

    assert Path(result.audio_path).exists()
    assert Path(result.audio_path).stat().st_size > 0
    assert result.actual_duration_ms > 0
    assert FakeCommunicate.save_calls == 1


def test_synthesize_ignores_target_duration_ms(tmp_path: Path, mock_edge_tts: None) -> None:
    provider = EdgeTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi", target_duration_ms=999_999)

    # actual_duration_ms reflects the real synthesized audio, not the ignored target
    assert result.actual_duration_ms != 999_999


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


def test_synthesize_network_failure_raises_runtime_error(
    tmp_path: Path, mock_edge_tts: None
) -> None:
    FakeCommunicate.fail_with = ConnectionError("no network")
    provider = EdgeTTSProvider(output_dir=str(tmp_path))

    with pytest.raises(RuntimeError, match="edge-tts request failed"):
        provider.synthesize("Hello.", "hi")
