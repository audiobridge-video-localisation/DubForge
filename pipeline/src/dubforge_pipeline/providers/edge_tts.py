"""EdgeTTSProvider: Microsoft Edge's unofficial online "read aloud" TTS service.

This provider calls the open-source `edge-tts` package, which talks to an
undocumented, unofficial Microsoft endpoint (the same one behind Edge's
"Read aloud" feature). It requires internet access, is not an officially
supported or licensed Microsoft API, and carries Terms of Service risk if
used beyond internal demos. Demo/internal use only - not for commercial
production.

The first take is spoken at TTS_RATE, the voice's normal pace. If target_duration_ms is
supplied and that take runs too long for it, the line is spoken again faster on top of
TTS_RATE (edge-tts's `rate` option), which keeps the voice cleaner than stretching the
finished audio. Any remaining gap is handled at export, within the same MAX_SPEEDUP.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from dubforge_contracts.models import MAX_SPEEDUP, AudioResult
from dubforge_pipeline.dub_fit import is_too_long, speedup_for

from .base import TTSProvider

logger = logging.getLogger(__name__)

# Each language maps to a small pool of (voice, gender) rather than one fixed voice, so
# distinct diarized speakers in the same media can be given distinct voices (speaker_index
# below), and the dominant/first speaker's gender can be steered by voice_gender.
_VOICE_POOL_BY_LANGUAGE: dict[str, list[tuple[str, str]]] = {
    "hi": [("hi-IN-SwaraNeural", "female"), ("hi-IN-MadhurNeural", "male")],
    "bn": [("bn-IN-TanishaaNeural", "female"), ("bn-IN-BashkarNeural", "male")],
}
_ALL_VOICES = {voice for pool in _VOICE_POOL_BY_LANGUAGE.values() for voice, _gender in pool}


def _resolve_voice(
    voice_profile: str, speaker_index: int | None = None, voice_gender: str | None = None
) -> str:
    # voice_profile is normally a language code (e.g. "hi"), mapped to a voice from that
    # language's pool. Passing an exact edge-tts voice name directly (e.g.
    # "hi-IN-SwaraNeural") overrides the language mapping, speaker_index, and voice_gender
    # entirely.
    if voice_profile in _ALL_VOICES:
        return voice_profile
    try:
        pool = _VOICE_POOL_BY_LANGUAGE[voice_profile]
    except KeyError:
        valid_options = ", ".join(sorted(_VOICE_POOL_BY_LANGUAGE))
        raise ValueError(
            f"Unsupported language/voice '{voice_profile}'; valid language codes: {valid_options}"
        ) from None
    if voice_gender is not None:
        # Put the requested gender's voice(s) first (stable sort keeps their relative
        # order), so speaker_index=0 - the dominant/first speaker - gets that gender, while
        # other speakers still land on a different voice from the rest of the pool.
        pool = sorted(pool, key=lambda item: item[1] != voice_gender)
    # No speaker info (e.g. an explicit test/override call): keep the previous,
    # single-voice behaviour by always using the pool's first voice.
    index = speaker_index if speaker_index is not None else 0
    return pool[index % len(pool)][0]


_DEFAULT_RATE = "+0%"
_RATE_PATTERN = re.compile(r"[+-][0-9]+%")


def _validate_rate(rate: str) -> str:
    # edge-tts expects a signed percentage such as "+20%" or "-10%".
    if not _RATE_PATTERN.fullmatch(rate):
        raise ValueError(
            f"Invalid TTS_RATE '{rate}'; expected a signed percentage like '+20%' or '-10%'"
        )
    return rate


def _rate_multiplier(rate: str) -> float:
    return 1 + int(rate.rstrip("%")) / 100


def _rate_option(multiplier: float) -> str:
    return f"{round((multiplier - 1) * 100):+d}%"


def _run_edge_tts_sync(text: str, voice: str, mp3_path: Path, rate: str = _DEFAULT_RATE) -> None:
    import edge_tts

    async def _synthesize() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
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
    def __init__(
        self, output_dir: str | None = None, timeout_s: int = 600, rate: str | None = None
    ) -> None:
        self.output_dir = output_dir or tempfile.gettempdir()
        self.timeout_s = timeout_s
        # Speaking rate; falls back to the TTS_RATE env var, then "+0%" (unchanged speed).
        self.rate = _validate_rate(rate or os.environ.get("TTS_RATE") or _DEFAULT_RATE)

    def synthesize(
        self,
        text: str,
        voice_profile: str,
        target_duration_ms: int | None = None,
        speaker_index: int | None = None,
        voice_gender: str | None = None,
    ) -> AudioResult:
        voice = _resolve_voice(voice_profile, speaker_index, voice_gender)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_wav_path = Path(tmp_dir) / "speech.wav"

            def take(speedup: float) -> int:
                # TTS_RATE is the voice's normal pace; a speed-up for a long line goes on top.
                rate = _rate_option(_rate_multiplier(self.rate) * speedup)
                mp3_path = Path(tmp_dir) / f"speech-{speedup:.2f}.mp3"
                try:
                    _run_edge_tts_sync(text, voice, mp3_path, rate)
                except Exception as exc:
                    raise RuntimeError(f"edge-tts request failed: {exc}") from exc

                if not mp3_path.exists() or mp3_path.stat().st_size == 0:
                    raise RuntimeError(
                        "edge-tts produced no audio output (check internet connectivity)"
                    )

                _convert_mp3_to_wav(mp3_path, tmp_wav_path, self.timeout_s)
                return _get_wav_duration_ms(tmp_wav_path, self.timeout_s)

            duration_ms = take(1.0)
            used_rate = 1.0
            if target_duration_ms is not None and is_too_long(duration_ms, target_duration_ms):
                rate = speedup_for(duration_ms, target_duration_ms, MAX_SPEEDUP)
                if rate > 1.0:
                    duration_ms = take(rate)
                    used_rate = rate

            fd, final_path = tempfile.mkstemp(suffix=".wav", dir=self.output_dir)
            os.close(fd)
            tmp_wav_path.replace(final_path)

        logger.info(
            "edge-tts synthesize voice=%s text_len=%d duration_ms=%d",
            voice,
            len(text),
            duration_ms,
        )
        return AudioResult(
            audio_path=final_path, actual_duration_ms=duration_ms, speech_rate=used_rate
        )
