import subprocess
import wave
from pathlib import Path

from dubforge_contracts.models import (
    AUDIO_MISMATCH_ABS_TOLERANCE_MS,
    AUDIO_MISMATCH_REL_TOLERANCE,
)

# How far dubbed speech may be sped up or slowed down to fit its slot. Past this it sounds
# rushed or drawn out, so the line is left as generated and shows up as a duration mismatch
# for a person to fix (shorter text, or a wider slot).
MIN_STRETCH = 0.7
MAX_STRETCH = 1.5


def _run_ffmpeg(cmd: list[str], timeout_s: int) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def extract_audio(video_path: str, output_path: str, timeout_s: int = 600) -> str:
    """Extract mono 16kHz WAV audio from a video file using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        output_path,
    ]
    _run_ffmpeg(cmd, timeout_s)
    if not Path(output_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_path


def wav_duration_ms(path: str) -> int:
    with wave.open(path, "rb") as wav_file:
        return round(wav_file.getnframes() / wav_file.getframerate() * 1000)


def fit_audio_duration(
    audio_path: str, current_ms: int, target_ms: int, timeout_s: int = 120
) -> tuple[str, int]:
    """Time-stretch dubbed audio (pitch preserved) so it fills its slot.

    Returns (path, duration_ms). Audio already within the mismatch tolerance, or needing
    more than MIN_STRETCH..MAX_STRETCH, is returned unchanged.
    """
    if current_ms <= 0 or target_ms <= 0:
        return audio_path, current_ms
    tolerance_ms = max(AUDIO_MISMATCH_ABS_TOLERANCE_MS, AUDIO_MISMATCH_REL_TOLERANCE * target_ms)
    if abs(current_ms - target_ms) <= tolerance_ms:
        return audio_path, current_ms

    tempo = current_ms / target_ms  # >1 speeds up (audio too long), <1 slows down
    if not MIN_STRETCH <= tempo <= MAX_STRETCH:
        return audio_path, current_ms

    source = Path(audio_path)
    fitted = source.with_name(f"{source.stem}.fit.wav")
    cmd = ["ffmpeg", "-y", "-i", str(source), "-filter:a", f"atempo={tempo:.4f}", str(fitted)]
    _run_ffmpeg(cmd, timeout_s)
    if not fitted.exists():
        raise RuntimeError("ffmpeg reported success but fitted audio is missing")
    source.unlink(missing_ok=True)
    return str(fitted), wav_duration_ms(str(fitted))
