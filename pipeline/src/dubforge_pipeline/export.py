import logging
from collections.abc import Sequence

from dubforge_contracts.models import TranscriptSegment

logger = logging.getLogger(__name__)

__all__ = [
    "format_srt_timestamp",
    "format_vtt_timestamp",
    "segments_to_srt",
    "segments_to_vtt",
]

_VTT_ESCAPES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
)


def _format_timestamp(ms: int, decimal_sep: str) -> str:
    if ms < 0:
        raise ValueError("ms must be >= 0")

    total_seconds, millis = divmod(ms, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{decimal_sep}{millis:03d}"


def format_srt_timestamp(ms: int) -> str:
    return _format_timestamp(ms, ",")


def format_vtt_timestamp(ms: int) -> str:
    return _format_timestamp(ms, ".")


def _clean_text(text: str) -> str:
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalised.split("\n")]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines).strip()


def _escape_vtt(text: str) -> str:
    for needle, replacement in _VTT_ESCAPES:
        text = text.replace(needle, replacement)
    return text


def _sorted_valid_segments(
    segments: Sequence[TranscriptSegment],
) -> tuple[list[tuple[TranscriptSegment, str]], int]:
    ordered = sorted(segments, key=lambda s: s.start_ms)

    valid: list[tuple[TranscriptSegment, str]] = []
    skipped = 0
    for segment in ordered:
        cleaned_text = _clean_text(segment.text)
        if not cleaned_text or segment.end_ms <= segment.start_ms:
            skipped += 1
            continue
        valid.append((segment, cleaned_text))

    return valid, skipped


def segments_to_srt(segments: Sequence[TranscriptSegment]) -> str:
    valid, skipped = _sorted_valid_segments(segments)

    blocks = []
    for index, (segment, cleaned_text) in enumerate(valid, start=1):
        start = format_srt_timestamp(segment.start_ms)
        end = format_srt_timestamp(segment.end_ms)
        blocks.append(f"{index}\n{start} --> {end}\n{cleaned_text}\n\n")

    logger.debug("segments_to_srt: cues written=%d skipped=%d", len(valid), skipped)
    return "".join(blocks)


def segments_to_vtt(segments: Sequence[TranscriptSegment]) -> str:
    valid, skipped = _sorted_valid_segments(segments)

    blocks = ["WEBVTT\n\n"]
    for segment, cleaned_text in valid:
        start = format_vtt_timestamp(segment.start_ms)
        end = format_vtt_timestamp(segment.end_ms)
        escaped_text = _escape_vtt(cleaned_text)
        blocks.append(f"{start} --> {end}\n{escaped_text}\n\n")

    logger.debug("segments_to_vtt: cues written=%d skipped=%d", len(valid), skipped)
    return "".join(blocks)
