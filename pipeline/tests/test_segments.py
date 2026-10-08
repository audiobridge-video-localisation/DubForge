from dubforge_contracts.models import SpeakerSegment, TranscriptSegment
from dubforge_pipeline.segments import UNKNOWN_SPEAKER, combine_segments


def test_combine_segments_perfectly_aligned() -> None:
    transcripts = [
        TranscriptSegment(start_ms=0, end_ms=2000, text="Hello"),
        TranscriptSegment(start_ms=2000, end_ms=4500, text="World"),
    ]
    speakers = [
        SpeakerSegment(start_ms=0, end_ms=2000, speaker_label="Speaker_0"),
        SpeakerSegment(start_ms=2000, end_ms=4500, speaker_label="Speaker_1"),
    ]

    segments = combine_segments(transcripts, speakers)

    assert [s.index for s in segments] == [0, 1]
    assert segments[0].speaker_label == "Speaker_0"
    assert segments[0].duration_ms == 2000
    assert segments[1].speaker_label == "Speaker_1"
    assert segments[1].duration_ms == 2500


def test_combine_segments_partial_overlap_picks_max_overlap() -> None:
    transcripts = [TranscriptSegment(start_ms=1000, end_ms=3000, text="Hi")]
    speakers = [
        SpeakerSegment(start_ms=0, end_ms=1500, speaker_label="A"),
        SpeakerSegment(start_ms=1500, end_ms=3000, speaker_label="B"),
    ]

    segments = combine_segments(transcripts, speakers)

    assert segments[0].speaker_label == "B"


def test_combine_segments_no_overlap_falls_back_to_unknown() -> None:
    transcripts = [TranscriptSegment(start_ms=0, end_ms=1000, text="Hi")]
    speakers = [SpeakerSegment(start_ms=5000, end_ms=6000, speaker_label="A")]

    segments = combine_segments(transcripts, speakers)

    assert segments[0].speaker_label == UNKNOWN_SPEAKER


def test_combine_segments_orders_by_start_ms() -> None:
    transcripts = [
        TranscriptSegment(start_ms=2000, end_ms=3000, text="Second"),
        TranscriptSegment(start_ms=0, end_ms=1000, text="First"),
    ]

    segments = combine_segments(transcripts, [])

    assert [s.text for s in segments] == ["First", "Second"]
    assert [s.index for s in segments] == [0, 1]
