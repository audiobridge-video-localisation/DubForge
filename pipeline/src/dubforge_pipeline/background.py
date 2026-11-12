"""Keep a video's background sound (music, room tone, effects) under the dub.

The original soundtrack is split into the voice and everything else with Demucs
(the optional `background` extra). The "everything else" track is kept next to the
video, so later exports reuse it, and the export lays it under the dub on the same
timeline as the picture. Without Demucs, or with KEEP_BACKGROUND=0, exports carry only
the dub, as before.
"""

import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Two stems is all a dub needs: the voice (dropped) and the rest (kept).
_DEMUCS_MODEL = "htdemucs"


def background_enabled() -> bool:
    if os.environ.get("KEEP_BACKGROUND", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return importlib.util.find_spec("demucs") is not None


def background_path(video_path: str) -> Path:
    """Where a video's separated background is kept (next to the video)."""
    video = Path(video_path)
    return video.with_name(f"{video.stem}.background.wav")


def voice_path(video_path: str) -> Path:
    """Where the original voice, separated with the background, is kept. The export uses
    it to set the dub to the speaker's loudness, so the voice/background balance holds."""
    video = Path(video_path)
    return video.with_name(f"{video.stem}.voice.wav")


def _run(cmd: list[str], timeout_s: int) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{cmd[0]} not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{cmd[0]} timed out after {timeout_s}s") from exc
    if result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {result.stderr[-2000:]}")


def separate_background(video_path: str, timeout_s: int = 3600) -> str | None:
    """The video's soundtrack without the voice, separated once and then reused.

    Returns None when background keeping is off or unavailable, or when separation
    fails; the export then carries the dub alone.
    """
    if not background_enabled():
        return None
    target = background_path(video_path)
    if target.exists():
        return str(target)
    try:
        with tempfile.TemporaryDirectory() as work:
            soundtrack = Path(work) / "soundtrack.wav"
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_path,
                    "-vn",
                    "-ac",
                    "2",
                    "-ar",
                    "44100",
                    str(soundtrack),
                ],
                timeout_s,
            )
            _run(
                [
                    sys.executable,
                    "-m",
                    "demucs",
                    "--two-stems",
                    "vocals",
                    "-n",
                    _DEMUCS_MODEL,
                    "-o",
                    work,
                    str(soundtrack),
                ],
                timeout_s,
            )
            stems = Path(work) / _DEMUCS_MODEL / soundtrack.stem
            separated = stems / "no_vocals.wav"
            if not separated.exists():
                raise RuntimeError("demucs finished but wrote no background track")
            if (stems / "vocals.wav").exists():
                shutil.move(str(stems / "vocals.wav"), voice_path(video_path))
            partial = target.with_name(f"{target.name}.part")
            shutil.move(str(separated), partial)
            partial.replace(target)
    except Exception:  # the dub alone is still a valid export
        logger.warning("Could not separate the background of %s", video_path, exc_info=True)
        return None
    return str(target)
