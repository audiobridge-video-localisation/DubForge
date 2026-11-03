from dubforge_contracts.models import Segment, SpeakerSegment, TranscriptSegment
from dubforge_pipeline.providers.base import TranslationProvider
from dubforge_pipeline.segments import (
    UNKNOWN_SPEAKER,
    choose_translation,
    combine_segments,
    translate_segments,
)


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


def _line(start_ms: int, end_ms: int, text: str = "Hi") -> Segment:
    return Segment(
        index=0,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        speaker_label="A",
        text=text,
    )


def test_choose_translation_keeps_the_top_choice_when_it_fits() -> None:
    # room 2000 ms, tolerance 500: 2500 ms available; 20 chars at 100 ms = 2000 ms
    assert choose_translation(["x" * 20, "x" * 5], room_ms=2000, ms_per_char=100) == "x" * 20


def test_choose_translation_takes_the_best_ranked_one_that_fits() -> None:
    candidates = ["x" * 40, "y" * 30, "z" * 20, "w" * 5]  # 4000, 3000, 2000, 500 ms
    assert choose_translation(candidates, room_ms=2000, ms_per_char=100) == "z" * 20


def test_choose_translation_takes_the_one_that_overshoots_least_when_none_fit() -> None:
    candidates = ["x" * 60, "y" * 40, "z" * 50]
    assert choose_translation(candidates, room_ms=1000, ms_per_char=100) == "y" * 40


class _AlternativesProvider(TranslationProvider):
    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        return "long " * 20

    def translate_candidates(
        self, text: str, src_lang: str, tgt_lang: str, count: int = 1
    ) -> list[str]:
        assert count > 1
        return ["long " * 20, "mid " * 8, "short"]


def test_translate_segments_uses_the_room_to_pick_a_fitting_alternative() -> None:
    # line 1 runs 0-1000 but the next starts at 2000, so its room is 2000 ms
    segments = [_line(0, 1000), _line(2000, 3000)]

    picked = translate_segments(segments, _AlternativesProvider(), "en", "hi", ms_per_char=60.0)

    # 100 chars = 6000 ms (too long), 32 chars = 1920 ms fits the 2000 ms room
    assert picked[0].translated_text == "mid " * 8
    # the last line only has its own 1000 ms (+300 tolerance): 32 chars = 1920 ms is too long
    assert picked[1].translated_text == "short"


def test_translate_segments_without_a_speech_rate_uses_the_first_translation() -> None:
    picked = translate_segments([_line(0, 1000)], _AlternativesProvider(), "en", "hi")

    assert picked[0].translated_text == "long " * 20
