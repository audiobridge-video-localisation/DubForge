from dubforge_contracts.models import Segment, SpeakerSegment, TranscriptSegment
from dubforge_pipeline.providers.base import TranslationProvider
from dubforge_pipeline.segments import UNKNOWN_SPEAKER, combine_segments, translate_segments


class _FakeTranslationProvider(TranslationProvider):
    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        return f"[{tgt_lang}] {text}"


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


def test_translate_segments_attaches_translated_text() -> None:
    segments = [
        Segment(index=0, start_ms=0, end_ms=1000, duration_ms=1000, speaker_label="A", text="Hi"),
        Segment(
            index=1,
            start_ms=1000,
            end_ms=2000,
            duration_ms=1000,
            speaker_label="B",
            text="Bye",
        ),
    ]

    translated = translate_segments(
        segments, _FakeTranslationProvider(), src_lang="en", tgt_lang="es"
    )

    assert [s.translated_text for s in translated] == ["[es] Hi", "[es] Bye"]
    assert [s.text for s in translated] == ["Hi", "Bye"]
    assert [s.index for s in translated] == [0, 1]
