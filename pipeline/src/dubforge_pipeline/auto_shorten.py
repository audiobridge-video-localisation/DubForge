"""Shorter wordings for a line whose dub still does not fit its room.

Speeding a voice up has a natural limit (dub_fit.MAX_NATURAL_RATE), so a line that is still
too long is fixed the way a person would fix it: with fewer words. The translator already
produced alternatives when it translated the line; the first few that are shorter and likely
to fit are tried, and the take that fits (or overshoots least) wins.
"""

from dubforge_pipeline.dub_fit import tolerance_ms

# how many shorter wordings are synthesised before giving up
MAX_REWRITE_TRIES = 2
# alternatives asked of the translator when looking for a shorter wording
CANDIDATES_TO_SEARCH = 8
# an alternative must be at most this share of the current text's length to be worth a take
MAX_LENGTH_SHARE = 0.9


def shorter_alternatives(
    candidates: list[str], current: str, room_ms: int, ms_per_char: float
) -> list[str]:
    """The wordings worth trying next, best first.

    Those predicted to fit keep the translator's own ranking (so quality is kept where it can
    be); the rest follow, shortest first.
    """
    limit_ms = room_ms + tolerance_ms(room_ms)
    shorter = [
        c
        for c in dict.fromkeys(candidates)
        if c and c != current and len(c) <= len(current) * MAX_LENGTH_SHARE
    ]
    fits = [c for c in shorter if len(c) * ms_per_char <= limit_ms]
    rest = sorted((c for c in shorter if c not in fits), key=len)
    return (fits + rest)[:MAX_REWRITE_TRIES]
