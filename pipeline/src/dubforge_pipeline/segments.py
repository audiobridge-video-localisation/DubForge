from dubforge_contracts.models import (
    Segment,
    SpeakerSegment,
    TranscriptSegment,
    segment_room_ms,
)
from dubforge_pipeline.dub_fit import tolerance_ms
from dubforge_pipeline.providers.base import TranslationProvider

UNKNOWN_SPEAKER = "Unknown"


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _speaker_for(transcript: TranscriptSegment, speakers: list[SpeakerSegment]) -> str:
    best_label = UNKNOWN_SPEAKER
    best_overlap = 0
    for speaker in speakers:
        overlap = _overlap_ms(
            transcript.start_ms, transcript.end_ms, speaker.start_ms, speaker.end_ms
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = speaker.speaker_label
    return best_label


def combine_segments(
    transcripts: list[TranscriptSegment], speakers: list[SpeakerSegment]
) -> list[Segment]:
    """Merge transcript and speaker segments into ordered, speaker-labeled segments."""
    ordered = sorted(transcripts, key=lambda t: t.start_ms)
    return [
        Segment(
            index=index,
            start_ms=transcript.start_ms,
            end_ms=transcript.end_ms,
            duration_ms=transcript.end_ms - transcript.start_ms,
            speaker_label=_speaker_for(transcript, speakers),
            text=transcript.text,
        )
        for index, transcript in enumerate(ordered)
    ]


# alternatives asked of the translator per line when we can judge how long they will sound
CANDIDATES_PER_LINE = 6


def choose_translation(candidates: list[str], room_ms: int, ms_per_char: float) -> str:
    """Pick the translation to use, best-ranked first.

    The translator's top choice wins unless it would take too long to say in the room it
    has. Then the highest-ranked alternative that fits is used; if none fits, the one that
    overshoots least (so the line needs the least rework).
    """
    available_ms = room_ms + tolerance_ms(room_ms)
    predicted = [len(c) * ms_per_char for c in candidates]
    for candidate, spoken_ms in zip(candidates, predicted, strict=True):
        if spoken_ms <= available_ms:
            return candidate
    return candidates[min(range(len(candidates)), key=lambda i: predicted[i])]


def translate_segments(
    segments: list[Segment],
    provider: TranslationProvider,
    src_lang: str,
    tgt_lang: str,
    ms_per_char: float | None = None,
) -> list[Segment]:
    """Attach a translated_text to each segment via the given provider.

    With `ms_per_char` (how long the voice takes per character), each line is translated
    with alternatives and the one that fits its room is chosen. Without it, the provider's
    first translation is used as is.
    """
    translated: list[Segment] = []
    for position, segment in enumerate(segments):
        if ms_per_char is None:
            text = provider.translate(segment.text, src_lang, tgt_lang)
        else:
            following = segments[position + 1].start_ms if position + 1 < len(segments) else None
            room_ms = segment_room_ms(segment.start_ms, segment.duration_ms, following)
            candidates = provider.translate_candidates(
                segment.text, src_lang, tgt_lang, count=CANDIDATES_PER_LINE
            )
            text = choose_translation(candidates, room_ms, ms_per_char)
        translated.append(segment.model_copy(update={"translated_text": text}))
    return translated
