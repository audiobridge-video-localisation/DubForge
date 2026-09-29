import pytest

from dubforge_pipeline.audio import extract_audio


def test_extract_audio_raises_on_missing_file() -> None:
    with pytest.raises(RuntimeError):
        extract_audio("nonexistent_video.mp4", "out.wav")
