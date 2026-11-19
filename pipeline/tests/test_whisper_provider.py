import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dubforge_pipeline.providers.whisper import WhisperSTTProvider


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float


class FakeWhisperModel:
    instances = 0

    def __init__(self, model_size: str, device: str, compute_type: str) -> None:
        FakeWhisperModel.instances += 1
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: str, **kwargs: Any) -> tuple[list[FakeSegment], object]:
        segments = [
            FakeSegment(start=0.0, end=2.0, text=" Hello there. ", avg_logprob=-0.1),
            FakeSegment(start=2.0, end=2.0, text="", avg_logprob=-0.2),
            FakeSegment(start=2.0, end=4.5, text="   ", avg_logprob=-0.3),
            FakeSegment(start=4.5, end=6.0, text="Second segment.", avg_logprob=-0.5),
        ]
        return segments, object()


@pytest.fixture(autouse=True)
def _reset_fake_model_counter() -> None:
    FakeWhisperModel.instances = 0


def test_transcribe_converts_and_filters_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisperModel)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")

    provider = WhisperSTTProvider()
    result = provider.transcribe(str(audio_path))

    assert len(result) == 2

    first, second = result
    assert first.start_ms == 0
    assert first.end_ms == 2000
    assert first.text == "Hello there."
    assert first.confidence == round(math.exp(-0.1), 4)

    assert second.start_ms == 4500
    assert second.end_ms == 6000
    assert second.text == "Second segment."
    assert second.confidence == round(math.exp(-0.5), 4)


def test_model_loaded_lazily_and_only_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisperModel)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")

    provider = WhisperSTTProvider()
    assert FakeWhisperModel.instances == 0

    provider.transcribe(str(audio_path))
    assert FakeWhisperModel.instances == 1

    provider.transcribe(str(audio_path))
    assert FakeWhisperModel.instances == 1


def test_transcribe_raises_on_missing_file(tmp_path: Path) -> None:
    provider = WhisperSTTProvider()
    with pytest.raises(RuntimeError):
        provider.transcribe(str(tmp_path / "missing.wav"))
