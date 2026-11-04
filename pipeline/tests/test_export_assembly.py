import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dubforge_contracts.models import MAX_VIDEO_SLOWDOWN
from dubforge_pipeline.export_assembly import (
    MAX_ATEMPO,
    VideoPiece,
    apply_tempo,
    build_dub_audio_track,
    build_timeline_video,
    encode_mp3,
    mux_mp4,
    plan_timeline,
    probe_duration_ms,
    probe_frame_rate,
    trim_silence,
)


def test_plan_timeline_without_lines_is_the_whole_video() -> None:
    timeline = plan_timeline([], 10_000)
    assert timeline.clips == []
    assert timeline.pieces == [VideoPiece(0, 10_000)]
    assert timeline.duration_ms == 10_000
    assert not timeline.changes_video


def test_plan_timeline_fitting_audio_changes_nothing() -> None:
    timeline = plan_timeline([(500, 1000, 900), (2000, 3000, 1000)], 5000)
    assert [(c.start_ms, c.tempo) for c in timeline.clips] == [(500, 1.0), (2000, 1.0)]
    assert timeline.duration_ms == 5000
    assert not timeline.changes_video


def test_plan_timeline_speeds_speech_up_first() -> None:
    # 1200ms in a 1000ms window: 1.2x faster speech, video untouched
    timeline = plan_timeline([(0, 1000, 1200), (1000, 2000, 500)], 3000)
    assert timeline.clips[0].tempo == pytest.approx(1.2)
    assert timeline.clips[1].start_ms == 1000
    assert not timeline.changes_video


def test_plan_timeline_slows_the_video_when_speech_alone_cannot_fit() -> None:
    # 1500ms in a 1000ms window: 1.25x speech leaves 1200ms, so the window plays 1.2x slower
    timeline = plan_timeline([(0, 1000, 1500), (1000, 2000, 500)], 3000)
    first = timeline.clips[0]
    assert first.tempo == MAX_ATEMPO
    assert timeline.pieces[0] == VideoPiece(0, 1000, pytest.approx(1.2), 0)
    # the next line starts where its (now later) window starts, so nothing overlaps
    assert timeline.clips[1].start_ms == 1200
    assert first.end_ms <= timeline.clips[1].start_ms
    assert timeline.duration_ms == 3200
    assert timeline.changes_video


def test_plan_timeline_holds_a_frame_for_whatever_is_left() -> None:
    # 3000ms in a 1000ms window: 1.25x speech = 2400ms; 1.25x slower video = 1250ms;
    # the last frame is held for the other 1150ms
    timeline = plan_timeline([(0, 1000, 3000), (1000, 2000, 500)], 3000)
    piece = timeline.pieces[0]
    assert piece.slowdown == MAX_VIDEO_SLOWDOWN
    assert piece.freeze_ms == 1150
    assert piece.output_ms == 2400
    assert timeline.clips[1].start_ms == 2400


def test_plan_timeline_never_overlaps_or_cuts_clips() -> None:
    lines = [(0, 900, 4000), (1000, 1800, 2600), (2000, 2500, 300), (2600, 4000, 5000)]
    timeline = plan_timeline(lines, 4500)
    ordered = sorted(timeline.clips, key=lambda c: c.start_ms)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        assert earlier.end_ms <= later.start_ms + 1
    assert ordered[-1].end_ms <= timeline.duration_ms + 1
    for clip, (_start, _end, audio_ms) in zip(timeline.clips, lines, strict=True):
        # audio is only ever sped up within the cap, never trimmed
        assert clip.end_ms - clip.start_ms == round(audio_ms / clip.tempo)
        assert 1.0 <= clip.tempo <= MAX_ATEMPO


def test_plan_timeline_last_line_past_the_video_end_freezes_the_end() -> None:
    timeline = plan_timeline([(0, 1000, 500), (4000, 4800, 2000)], 5000)
    last = timeline.pieces[-1]
    assert last.source_end_ms == 5000
    assert timeline.duration_ms >= timeline.clips[1].end_ms
    assert last.freeze_ms > 0 or last.slowdown > 1


def test_plan_timeline_keeps_input_order_for_unsorted_lines() -> None:
    timeline = plan_timeline([(2000, 3000, 500), (0, 1000, 1200), (1000, 2000, 500)], 5000)
    assert [c.start_ms for c in timeline.clips] == [2000, 0, 1000]
    assert timeline.clips[1].tempo == pytest.approx(1.2)


def test_plan_timeline_subtitles_last_as_long_as_the_speech_or_the_clip() -> None:
    timeline = plan_timeline([(0, 800, 400), (1000, 2000, 2400)], 3000)
    short, long = timeline.clips
    assert short.subtitle_end_ms == 800  # the clip ends early; the line still reads on
    assert long.subtitle_end_ms == long.end_ms


def test_apply_tempo_rejects_non_positive_tempo(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        apply_tempo("in.wav", str(tmp_path / "out.wav"), 0)


def test_apply_tempo_raises_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        apply_tempo("in.wav", str(tmp_path / "out.wav"), 1.2, timeout_s=1)


def test_apply_tempo_raises_on_missing_input(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        apply_tempo(str(tmp_path / "nonexistent.wav"), str(tmp_path / "out.wav"), 1.2)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_apply_tempo_real_shortens_duration(tmp_path: Path) -> None:
    source = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(source)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = tmp_path / "fast.wav"

    apply_tempo(str(source), str(output), 1.25)

    assert output.exists()
    # 2000ms / 1.25 = 1600ms
    assert abs(probe_duration_ms(str(output)) - 1600) <= 60


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
    assert "normalize=0" in joined  # clips never overlap: keep them at full volume


def test_encode_mp3_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        encode_mp3(str(tmp_path / "nonexistent.wav"), str(tmp_path / "out.mp3"))


def test_mux_mp4_adds_a_subtitle_track_when_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[str] = []
    output_path = tmp_path / "out.mp4"

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"format": {"duration": "3.0"}}')
        captured.extend(cmd)
        output_path.write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    mux_mp4("v.mp4", "a.wav", str(output_path), subtitles_path="s.srt", subtitle_language="hin")

    joined = " ".join(captured)
    assert "-map 2:s:0 -c:s mov_text" in joined
    assert "language=hin" in joined
    assert "-t 3.000" in joined
    assert "-shortest" not in joined


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


def _make_video(path: Path, seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=160x120:rate=25:duration={seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_build_timeline_video_real_matches_the_planned_length(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    _make_video(video, 3)
    assert probe_frame_rate(str(video)) == pytest.approx(25)
    # a second at normal speed, a second slowed 1.2x and held 400ms, then a second as is
    pieces = [VideoPiece(0, 1000), VideoPiece(1000, 2000, 1.2, 400), VideoPiece(2000, 3000)]
    output = tmp_path / "out.mp4"

    build_timeline_video(str(video), pieces, str(tmp_path), str(output))

    assert abs(probe_duration_ms(str(output)) - sum(p.output_ms for p in pieces)) <= 40


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_trim_silence_real_removes_quiet_edges(tmp_path: Path) -> None:
    clip = tmp_path / "clip.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono:d=0.5",
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
            "-ac",
            "1",
            str(clip),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    output = tmp_path / "trimmed.wav"

    trim_silence(str(clip), str(output))

    assert abs(probe_duration_ms(str(output)) - 1000) <= 60


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mux_mp4_real_keeps_the_full_video_with_subtitles(tmp_path: Path) -> None:
    video = tmp_path / "in.mp4"
    _make_video(video, 3)
    wav = tmp_path / "dub.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=3", str(wav)],
        capture_output=True,
        text=True,
        check=True,
    )
    srt = tmp_path / "dub.srt"
    # the only cue ends well before the video does
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nनमस्ते\n", encoding="utf-8")
    output = tmp_path / "out.mp4"

    mux_mp4(str(video), str(wav), str(output), subtitles_path=str(srt), subtitle_language="hin")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    kinds = sorted(s["codec_type"] for s in json.loads(probe.stdout)["streams"])
    assert kinds == ["audio", "subtitle", "video"]
    assert abs(probe_duration_ms(str(output)) - 3000) <= 100


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_build_dub_audio_track_real_keeps_each_clip_at_full_volume(tmp_path: Path) -> None:
    clips = []
    for index in range(6):
        clip = tmp_path / f"seg{index}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=16000:duration=0.5",
                "-af",
                "volume=0.5",
                str(clip),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        clips.append((index * 1000, str(clip)))
    output = tmp_path / "dub.wav"

    build_dub_audio_track(clips, 6000, str(output))

    def peak_db(path: str) -> float:
        stats = subprocess.run(
            ["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stderr
        return float(stats.split("max_volume:")[1].split("dB")[0])

    # with seven inputs, amix's default would drop every clip by about 17 dB
    assert peak_db(str(output)) >= peak_db(clips[0][1]) - 1
