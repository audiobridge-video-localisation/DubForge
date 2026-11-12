import subprocess
from pathlib import Path


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
