import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dubforge_pipeline.export_assembly import (
    build_dub_audio_track,
    encode_mp3,
    mux_mp4,
    probe_duration_ms,
)


def test_probe_duration_ms_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        probe_duration_ms(str(tmp_path / "nonexistent.wav"))


def test_probe_duration_ms_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        probe_duration_ms("in.wav", timeout_s=1)


def test_build_dub_audio_track_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        build_dub_audio_track([(0, "seg.wav")], 1000, str(tmp_path / "out.wav"))


def test_build_dub_audio_track_raises_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        build_dub_audio_track([(0, "seg.wav")], 1000, str(tmp_path / "out.wav"), timeout_s=1)


def test_build_dub_audio_track_invokes_ffmpeg_with_expected_filter_complex(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_cmd: list[str] = []
    output_path = tmp_path / "out.wav"

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        output_path.write_bytes(b"fake wav")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    build_dub_audio_track(
        [(0, "seg0.wav"), (2500, "seg1.wav")], 5000, str(output_path), timeout_s=10
    )

    assert "seg0.wav" in captured_cmd
    assert "seg1.wav" in captured_cmd
    joined = " ".join(captured_cmd)
    assert "anullsrc=channel_layout=mono:sample_rate=16000:d=5.0" in joined
    assert "adelay=0:all=1" in joined
    assert "adelay=2500:all=1" in joined
    assert "amix=inputs=3:duration=first" in joined


def test_encode_mp3_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        encode_mp3(str(tmp_path / "nonexistent.wav"), str(tmp_path / "out.mp3"))


def test_mux_mp4_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        mux_mp4(
            str(tmp_path / "nonexistent.mp4"),
            str(tmp_path / "nonexistent.wav"),
            str(tmp_path / "out.mp4"),
        )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_build_dub_audio_track_real_produces_correct_duration(tmp_path: Path) -> None:
    seg0 = tmp_path / "seg0.wav"
    seg1 = tmp_path / "seg1.wav"
    for path, freq in [(seg0, 440), (seg1, 880)]:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={freq}:duration=1",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    output_path = tmp_path / "dub.wav"
    build_dub_audio_track([(0, str(seg0)), (2000, str(seg1))], 3000, str(output_path))

    assert output_path.exists()
    duration_ms = probe_duration_ms(str(output_path))
    assert abs(duration_ms - 3000) <= 50


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_encode_mp3_real_produces_valid_mp3(tmp_path: Path) -> None:
    wav_path = tmp_path / "in.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(wav_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    output_path = tmp_path / "out.mp3"
    encode_mp3(str(wav_path), str(output_path))

    assert output_path.exists()
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "json",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    codec = json.loads(probe.stdout)["streams"][0]["codec_name"]
    assert codec == "mp3"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mux_mp4_real_copies_video_stream(tmp_path: Path) -> None:
    video_path = tmp_path / "in.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    wav_path = tmp_path / "dub.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1", str(wav_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    output_path = tmp_path / "out.mp4"
    mux_mp4(str(video_path), str(wav_path), str(output_path))

    assert output_path.exists()
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name",
            "-of",
            "json",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    codecs = {s["codec_type"]: s["codec_name"] for s in streams}
    # -c:a aac is explicit and deterministic; -c:v copy preserves whatever
    # codec ffmpeg chose for the source fixture, which varies by build, so
    # only presence is asserted for video.
    assert codecs["audio"] == "aac"
    assert "video" in codecs
