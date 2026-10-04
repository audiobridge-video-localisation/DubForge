from dubforge_contracts.models import Segment, SpeakerSegment, TranscriptSegment

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
