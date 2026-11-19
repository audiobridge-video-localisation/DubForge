import logging
import re

from dubforge_contracts.models import TranscriptSegment

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def _duration_ms(segment: TranscriptSegment) -> int:
    return segment.end_ms - segment.start_ms


def _merge_pair(first: TranscriptSegment, second: TranscriptSegment) -> TranscriptSegment:
    start_ms = min(first.start_ms, second.start_ms)
    end_ms = max(first.end_ms, second.end_ms)

    parts = [_WHITESPACE_RE.sub(" ", p.strip()) for p in (first.text, second.text)]
    text = " ".join(p for p in parts if p)

    first_duration = _duration_ms(first)
    second_duration = _duration_ms(second)
    total_duration = first_duration + second_duration

    confidence: float | None
    if first.confidence is None and second.confidence is None:
        confidence = None
    else:
        first_conf = first.confidence if first.confidence is not None else 0.0
        second_conf = second.confidence if second.confidence is not None else 0.0
        if total_duration > 0:
            weighted = (
                first_conf * first_duration + second_conf * second_duration
            ) / total_duration
            confidence = round(weighted, 4)
        else:
            confidence = round((first_conf + second_conf) / 2, 4)

    return TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text, confidence=confidence)


def merge_short_segments(
    segments: list[TranscriptSegment],
    min_duration_ms: int = 500,
    max_gap_ms: int = 1000,
    max_merged_duration_ms: int = 15000,
) -> list[TranscriptSegment]:
    if min_duration_ms < 0:
        raise ValueError("min_duration_ms must be >= 0")
    if max_gap_ms < 0:
        raise ValueError("max_gap_ms must be >= 0")
    if max_merged_duration_ms <= 0:
        raise ValueError("max_merged_duration_ms must be > 0")

    if not segments:
        return []

    result = sorted(
        (s.model_copy() for s in segments),
        key=lambda s: s.start_ms,
    )

    i = 0
    while i < len(result):
        current = result[i]
        if _duration_ms(current) >= min_duration_ms:
            i += 1
            continue

        merged_into_prev = False
        if i > 0:
            prev = result[i - 1]
            gap = current.start_ms - prev.end_ms
            candidate = _merge_pair(prev, current)
            if gap <= max_gap_ms and _duration_ms(candidate) <= max_merged_duration_ms:
                result[i - 1] = candidate
                del result[i]
                merged_into_prev = True
                i -= 1

        if merged_into_prev:
            continue

        if i + 1 < len(result):
            nxt = result[i + 1]
            gap = nxt.start_ms - current.end_ms
            candidate = _merge_pair(current, nxt)
            if gap <= max_gap_ms and _duration_ms(candidate) <= max_merged_duration_ms:
                result[i] = candidate
                del result[i + 1]
                continue

        i += 1

    logger.debug("merge_short_segments: %d segments -> %d segments", len(segments), len(result))
    return result
