"""EdgeTTSProvider: Microsoft Edge's unofficial online "read aloud" TTS service.

This provider calls the open-source `edge-tts` package, which talks to an
undocumented, unofficial Microsoft endpoint (the same one behind Edge's
"Read aloud" feature). It requires internet access, is not an officially
supported or licensed Microsoft API, and carries Terms of Service risk if
used beyond internal demos. Demo/internal use only - not for commercial
production.

If target_duration_ms is supplied it is ignored - this provider does not
perform time-stretching or duration matching against a target; that is
handled later in the pipeline.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from dubforge_contracts.models import AudioResult

from .base import TTSProvider

logger = logging.getLogger(__name__)

_VOICE_BY_LANGUAGE = {
    "hi": "hi-IN-SwaraNeural",
    "bn": "bn-IN-TanishaaNeural",
}


def _resolve_voice(voice_profile: str) -> str:
    # voice_profile is normally a language code (e.g. "hi"), mapped to a
    # fixed edge-tts voice. Passing an exact edge-tts voice name directly
    # (e.g. "hi-IN-SwaraNeural") overrides the language mapping.
    if voice_profile in _VOICE_BY_LANGUAGE.values():
        return voice_profile
    try:
        return _VOICE_BY_LANGUAGE[voice_profile]
    except KeyError:
        valid_options = ", ".join(sorted(_VOICE_BY_LANGUAGE))
        raise ValueError(
            f"Unsupported language/voice '{voice_profile}'; valid language codes: {valid_options}"
        ) from None


def _run_edge_tts_sync(text: str, voice: str, mp3_path: Path) -> None:
    import edge_tts

    async def _synthesize() -> None:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(mp3_path))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running in this thread - safe to drive synchronously.
        asyncio.run(_synthesize())
        return

    # Already inside a running event loop (e.g. called from async code):
    # run edge-tts on a separate thread with its own loop.
    exception: BaseException | None = None

    def _thread_target() -> None:
        nonlocal exception
        try:
            asyncio.run(_synthesize())
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread below
            exception = exc

    thread = threading.Thread(target=_thread_target)
    thread.start()
    thread.join()
    if exception is not None:
        raise exception


def _convert_mp3_to_wav(mp3_path: Path, wav_path: Path, timeout_s: int) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp3_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not wav_path.exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")


def _get_wav_duration_ms(wav_path: Path, timeout_s: int) -> int:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(wav_path),
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


class EdgeTTSProvider(TTSProvider):
    def __init__(self, output_dir: str | None = None, timeout_s: int = 600) -> None:
        self.output_dir = output_dir or tempfile.gettempdir()
        self.timeout_s = timeout_s

    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        voice = _resolve_voice(voice_profile)

        with tempfile.TemporaryDirectory() as tmp_dir:
            mp3_path = Path(tmp_dir) / "speech.mp3"
            tmp_wav_path = Path(tmp_dir) / "speech.wav"

            try:
                _run_edge_tts_sync(text, voice, mp3_path)
            except Exception as exc:
                raise RuntimeError(f"edge-tts request failed: {exc}") from exc

            if not mp3_path.exists() or mp3_path.stat().st_size == 0:
                raise RuntimeError(
                    "edge-tts produced no audio output (check internet connectivity)"
                )

            _convert_mp3_to_wav(mp3_path, tmp_wav_path, self.timeout_s)
            duration_ms = _get_wav_duration_ms(tmp_wav_path, self.timeout_s)

            fd, final_path = tempfile.mkstemp(suffix=".wav", dir=self.output_dir)
            os.close(fd)
            tmp_wav_path.replace(final_path)

        logger.info(
            "edge-tts synthesize voice=%s text_len=%d duration_ms=%d",
            voice,
            len(text),
            duration_ms,
        )
        return AudioResult(audio_path=final_path, actual_duration_ms=duration_ms)
