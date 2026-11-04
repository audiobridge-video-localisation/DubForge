import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Never speed speech up by more than this; beyond it the clip is left long.
MAX_ATEMPO = 1.25
# Overruns up to this fraction of the available room are left untouched.
NEGLIGIBLE_OVERRUN = 0.10


@dataclass(frozen=True)
class SegmentPlacement:
    start_ms: int
    tempo: float


def plan_placements(
    segments: list[tuple[int, int, int]], total_duration_ms: int
) -> list[SegmentPlacement]:
    """Decide where each dubbed clip starts and how much to speed it up.

    `segments` holds (start_ms, end_ms, audio_duration_ms) and may be in any
    order; the result is in the same order as the input. Clips are processed
    in start order. A clip's room runs from its (possibly pushed) start to the
    next segment's original start (the video end for the last one). Clips that
    overrun their room by more than NEGLIGIBLE_OVERRUN are sped up to fit,
    capped at MAX_ATEMPO; audio is never trimmed. If a clip still runs past
    its room, the following clip is pushed later rather than overlapped.
    """
    order = sorted(range(len(segments)), key=lambda i: segments[i][0])
    placements: list[SegmentPlacement | None] = [None] * len(segments)
    latest_start_ms = max(total_duration_ms - 1, 0)

    earliest_start_ms = 0
    for position, index in enumerate(order):
        original_start_ms, _end_ms, audio_ms = segments[index]
        start_ms = min(max(original_start_ms, earliest_start_ms), latest_start_ms)

        if position + 1 < len(order):
            room_end_ms = segments[order[position + 1]][0]
        else:
            room_end_ms = total_duration_ms
        room_ms = room_end_ms - start_ms

        tempo = 1.0
        if audio_ms > 0:
            if room_ms <= 0:
                tempo = MAX_ATEMPO
            else:
                ratio = audio_ms / room_ms
                if ratio > 1 + NEGLIGIBLE_OVERRUN + 1e-9:
                    tempo = min(ratio, MAX_ATEMPO)

        placements[index] = SegmentPlacement(start_ms=start_ms, tempo=tempo)
        earliest_start_ms = start_ms + round(audio_ms / tempo)

    return [placement for placement in placements if placement is not None]


def probe_duration_ms(path: str, timeout_s: int = 60) -> int:
    """Return a media file's duration in milliseconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    duration_s = float(json.loads(result.stdout)["format"]["duration"])
    return round(duration_s * 1000)


def apply_tempo(input_path: str, output_path: str, tempo: float, timeout_s: int = 600) -> str:
    """Speed audio up (tempo > 1) or down with ffmpeg's pitch-preserving atempo filter."""
    if tempo <= 0:
        raise ValueError(f"tempo must be > 0, got {tempo}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-filter:a",
        f"atempo={tempo:.4f}",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_path


def build_dub_audio_track(
    segment_audio: list[tuple[int, str]],
    total_duration_ms: int,
    output_wav_path: str,
    timeout_s: int = 600,
) -> str:
    """Build one continuous mono 16kHz WAV spanning total_duration_ms, with
    each segment's audio placed at its start_ms offset.

    Uses a silent base track (anullsrc, trimmed to total_duration_ms via its
    own `d=` parameter) mixed with every segment clip delayed to its offset
    via the `adelay` filter, combined with `amix` anchored to the silent
    base track's duration.
    """
    total_duration_s = total_duration_ms / 1000
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate=16000:d={total_duration_s}",
    ]
    for _, audio_path in segment_audio:
        cmd += ["-i", audio_path]

    filter_parts = []
    mix_inputs = ["[0:a]"]
    for index, (start_ms, _) in enumerate(segment_audio, start=1):
        label = f"d{index}"
        filter_parts.append(f"[{index}:a]adelay={start_ms}:all=1[{label}]")
        mix_inputs.append(f"[{label}]")
    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0[aout]"
    )
    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-ac",
        "1",
        "-ar",
        "16000",
        output_wav_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_wav_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_wav_path


def encode_mp3(wav_path: str, output_mp3_path: str, timeout_s: int = 600) -> str:
    """Encode a WAV file to MP3 (libmp3lame)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        wav_path,
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        output_mp3_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_mp3_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_mp3_path


def mux_mp4(
    video_path: str, dub_audio_wav_path: str, output_mp4_path: str, timeout_s: int = 600
) -> str:
    """Mux a dub audio track onto the original video, replacing its audio
    entirely. The video stream is copied untouched (no re-encode)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        dub_audio_wav_path,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        output_mp4_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_mp4_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_mp4_path
