import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dubforge_pipeline.audio import extract_audio


def test_extract_audio_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        extract_audio("nonexistent_video.mp4", str(tmp_path / "out.wav"))


def test_extract_audio_raises_on_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=2",
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
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=channels,sample_rate",
            "-of",
            "json",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream_info = json.loads(probe.stdout)["streams"][0]
    assert stream_info["channels"] == 1
    assert stream_info["sample_rate"] == "16000"


def _silent_wav(path: Path, duration_ms: int) -> str:
    import wave

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * (16000 * duration_ms // 1000))
    return str(path)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.parametrize(
    ("current_ms", "target_ms"),
    [(3200, 2400), (3300, 2400), (1500, 1080)],
)
def test_fit_audio_duration_speeds_up_audio_that_is_too_long(
    tmp_path: Path, current_ms: int, target_ms: int
) -> None:
    from dubforge_contracts.models import (
        AUDIO_MISMATCH_ABS_TOLERANCE_MS,
        AUDIO_MISMATCH_REL_TOLERANCE,
    )
    from dubforge_pipeline.audio import fit_audio_duration

    path = _silent_wav(tmp_path / "dub.wav", current_ms)

    fitted, duration_ms = fit_audio_duration(path, current_ms, target_ms)

    tolerance_ms = max(AUDIO_MISMATCH_ABS_TOLERANCE_MS, AUDIO_MISMATCH_REL_TOLERANCE * target_ms)
    assert target_ms <= duration_ms <= target_ms + tolerance_ms  # fits, and not rushed past it
    assert duration_ms < current_ms
    assert Path(fitted).exists()
    assert not Path(path).exists()  # replaced by the fitted file


@pytest.mark.parametrize(("current_ms", "target_ms"), [(2000, 2200), (2400, 2000), (1000, 4000)])
def test_fit_audio_duration_leaves_audio_that_fits_or_is_short(
    tmp_path: Path, current_ms: int, target_ms: int
) -> None:
    from dubforge_pipeline.audio import fit_audio_duration

    path = _silent_wav(tmp_path / "dub.wav", current_ms)

    assert fit_audio_duration(path, current_ms, target_ms) == (path, current_ms)


@pytest.mark.parametrize(("current_ms", "target_ms"), [(3440, 1660), (6000, 2000), (5488, 2880)])
def test_fit_audio_duration_leaves_audio_that_cannot_fit_in_range(
    tmp_path: Path, current_ms: int, target_ms: int
) -> None:
    from dubforge_pipeline.audio import fit_audio_duration

    path = _silent_wav(tmp_path / "dub.wav", current_ms)

    assert fit_audio_duration(path, current_ms, target_ms) == (path, current_ms)
