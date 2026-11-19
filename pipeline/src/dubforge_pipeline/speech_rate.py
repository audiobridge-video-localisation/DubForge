"""How long a voice takes to say a character, learned from the audio it has produced.

Translation happens before any audio exists, but choosing a translation that will fit
needs an idea of how long it will take to speak. Rather than a fixed guess, every finished
take updates a running average for that voice, kept in a small file next to the media.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Used until a voice has produced anything. Measured on the Hindi MMS voice (about 90 ms per
# character); it is replaced by real measurements after the first few lines.
DEFAULT_MS_PER_CHAR = 90.0
# Weight of each new take in the running average.
SMOOTHING = 0.2

_FILE_NAME = ".speech_rate.json"


def _path(storage_root: str) -> Path:
    return Path(storage_root) / _FILE_NAME


def _read(storage_root: str) -> dict[str, float]:
    try:
        raw = json.loads(_path(storage_root).read_text())
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in raw.items() if isinstance(v, int | float) and v > 0}


def get_ms_per_char(storage_root: str, voice_key: str) -> float:
    return _read(storage_root).get(voice_key, DEFAULT_MS_PER_CHAR)


def record_take(
    storage_root: str, voice_key: str, text: str, duration_ms: int, speech_rate: float
) -> None:
    """Fold one finished take into the voice's average, at its natural (1.0x) pace."""
    chars = len(text.strip())
    if chars == 0 or duration_ms <= 0 or speech_rate <= 0:
        return
    natural_ms_per_char = duration_ms * speech_rate / chars
    rates = _read(storage_root)
    previous = rates.get(voice_key)
    rates[voice_key] = (
        natural_ms_per_char
        if previous is None
        else previous + SMOOTHING * (natural_ms_per_char - previous)
    )
    try:
        fd, tmp = tempfile.mkstemp(dir=storage_root, suffix=".tmp")
        with os.fdopen(fd, "w") as handle:
            json.dump(rates, handle)
        os.replace(tmp, _path(storage_root))
    except OSError:
        logger.warning("could not save the speech rate for %s", voice_key)
