"""How much a dubbed line may be sped up, and when it needs to be.

The numbers here come from the mismatch rule in dubforge_contracts, not from separate
constants, so changing the tolerance there changes what the synthesisers aim for.
"""

from dubforge_contracts.models import (
    AUDIO_MISMATCH_ABS_TOLERANCE_MS,
    AUDIO_MISMATCH_REL_TOLERANCE,
)

# How much faster a voice is asked to speak when a take runs long. Past about 1.2x speech
# stops sounding natural (Descript's listening tests), so this stays modest; the rest of
# the gap is for shorter text, not a faster voice.
MAX_NATURAL_RATE = 1.3
# Aim this far into the tolerance, so a take is not left right on the edge.
TARGET_TOLERANCE_SHARE = 0.5


def tolerance_ms(target_ms: int) -> float:
    return max(AUDIO_MISMATCH_ABS_TOLERANCE_MS, AUDIO_MISMATCH_REL_TOLERANCE * target_ms)


def is_too_long(current_ms: int, target_ms: int) -> bool:
    return current_ms - target_ms > tolerance_ms(target_ms)


def speedup_for(current_ms: int, target_ms: int, max_rate: float) -> float:
    """Speed-up (>= 1) that brings `current_ms` to just inside the tolerance, capped."""
    if current_ms <= 0 or target_ms <= 0:
        return 1.0
    aim_ms = target_ms + tolerance_ms(target_ms) * TARGET_TOLERANCE_SHARE
    return min(max(current_ms / aim_ms, 1.0), max_rate)
