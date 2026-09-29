import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dubforge_pipeline.audio import extract_audio


def test_extract_audio_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        extract_audio("nonexistent_video.mp4", str(tmp_path / "out.wav"))


def test_extract_audio_raises_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        extract_audio("in.mp4", str(tmp_path / "out.wav"), timeout_s=1)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_extract_audio_produces_mono_16khz_wav(tmp_path: Path) -> None:
    video_path = tmp_path / "in.mp4"
    output_path = tmp_path / "out.wav"

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
            "-shortest",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = extract_audio(str(video_path), str(output_path))

    assert result == str(output_path)
    assert output_path.exists()

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=channels,sample_rate",
            "-of", "json",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream_info = json.loads(probe.stdout)["streams"][0]
    assert stream_info["channels"] == 1
    assert stream_info["sample_rate"] == "16000"
