import os
import shutil
import subprocess
from pathlib import Path

import pytest

from dubforge_pipeline import background
from dubforge_pipeline.background import background_path, separate_background


def test_background_is_kept_next_to_the_video() -> None:
    assert background_path("/data/proj/clip.mp4") == Path("/data/proj/clip.background.wav")


def test_keep_background_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setenv("KEEP_BACKGROUND", "0")
    assert not background.background_enabled()
    monkeypatch.setenv("KEEP_BACKGROUND", "1")
    assert background.background_enabled()


def test_without_demucs_the_export_keeps_the_dub_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("KEEP_BACKGROUND", raising=False)
    monkeypatch.setattr(background.importlib.util, "find_spec", lambda _name: None)
    assert separate_background(str(tmp_path / "clip.mp4")) is None


def test_a_separated_background_is_reused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(background, "background_enabled", lambda: True)
    video = tmp_path / "clip.mp4"
    cached = background_path(str(video))
    cached.write_bytes(b"already separated")

    def _must_not_run(*_a: object, **_k: object) -> None:
        raise AssertionError("separation must not run again")

    monkeypatch.setattr(background, "_run", _must_not_run)
    assert separate_background(str(video)) == str(cached)


def test_a_failed_separation_falls_back_to_the_dub_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(background, "background_enabled", lambda: True)

    def _fails(*_a: object, **_k: object) -> None:
        raise RuntimeError("demucs failed")

    monkeypatch.setattr(background, "_run", _fails)
    video = tmp_path / "clip.mp4"
    assert separate_background(str(video)) is None
    assert not background_path(str(video)).exists()


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None
    or not background.background_enabled()
    or os.environ.get("DUBFORGE_SLOW_TESTS") != "1",
    reason="needs ffmpeg, the background extra and DUBFORGE_SLOW_TESTS=1 (downloads a model)",
)
def test_separate_background_real_returns_a_track_as_long_as_the_video(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x120:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=2",
            "-shortest",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    track = separate_background(str(video))

    assert track is not None
    assert background.voice_path(str(video)).exists()  # kept for the dub's loudness
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", track],
        capture_output=True,
        text=True,
        check=True,
    )
    assert abs(float(probe.stdout) - 2.0) < 0.1
