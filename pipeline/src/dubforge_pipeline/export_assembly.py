import json
import subprocess
from pathlib import Path


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
