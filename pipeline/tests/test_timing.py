import pytest

from dubforge_contracts.models import TranscriptSegment
from dubforge_pipeline.timing import merge_short_segments


def seg(
    start_ms: int, end_ms: int, text: str, confidence: float | None = None
) -> TranscriptSegment:
    return TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text, confidence=confidence)


def test_empty_list_returns_empty() -> None:
    assert merge_short_segments([]) == []


def test_no_short_segments_unchanged() -> None:
    segments = [
        seg(0, 1000, "Hello there."),
        seg(1000, 2500, "This is a test."),
    ]
    result = merge_short_segments(segments)
    assert result == segments


def test_short_segment_in_middle_merges_into_previous() -> None:
    segments = [
        seg(0, 1000, "First."),
        seg(1000, 1200, "Uh."),
        seg(1200, 2500, "Last."),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 2
    assert result[0].start_ms == 0
    assert result[0].end_ms == 1200
    assert result[0].text == "First. Uh."
    assert result[1] == segments[2]


def test_first_segment_short_merges_forward() -> None:
    segments = [
        seg(0, 100, "Uh."),
        seg(100, 1500, "First real segment."),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 1
    assert result[0].start_ms == 0
    assert result[0].end_ms == 1500
    assert result[0].text == "Uh. First real segment."


def test_last_segment_short_merges_backward() -> None:
    segments = [
        seg(0, 1500, "First real segment."),
        seg(1500, 1600, "Uh."),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 1
    assert result[0].start_ms == 0
    assert result[0].end_ms == 1600
    assert result[0].text == "First real segment. Uh."


def test_gap_larger_than_max_gap_not_merged() -> None:
    segments = [
        seg(0, 1000, "First."),
        seg(3000, 3200, "Short but far."),
    ]
    result = merge_short_segments(segments, min_duration_ms=500, max_gap_ms=1000)
    assert len(result) == 2
    assert result[0] == segments[0]
    assert result[1] == segments[1]


def test_merged_duration_cap_respected() -> None:
    segments = [
        seg(0, 14900, "Long segment."),
        seg(14900, 15100, "Short."),
    ]
    result = merge_short_segments(
        segments, min_duration_ms=500, max_gap_ms=1000, max_merged_duration_ms=15000
    )
    assert len(result) == 2
    assert result[0] == segments[0]
    assert result[1] == segments[1]


def test_chain_of_three_short_segments_collapses_to_one() -> None:
    segments = [
        seg(0, 200, "A"),
        seg(200, 400, "B"),
        seg(400, 600, "C"),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 1
    assert result[0].start_ms == 0
    assert result[0].end_ms == 600
    assert result[0].text == "A B C"


def test_text_joining_strips_and_collapses_whitespace() -> None:
    segments = [
        seg(0, 1000, "  Hello   there  "),
        seg(1000, 1200, "  "),
        seg(1200, 2500, "Goodbye."),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 2
    assert result[0].start_ms == 0
    assert result[0].end_ms == 1200
    assert result[0].text == "Hello there"
    assert result[1] == segments[2]


def test_confidence_is_duration_weighted_average() -> None:
    segments = [
        seg(0, 1000, "First.", confidence=0.8),
        seg(1000, 1200, "Short.", confidence=0.4),
    ]
    result = merge_short_segments(segments, min_duration_ms=500)
    assert len(result) == 1
    expected = round((0.8 * 1000 + 0.4 * 200) / 1200, 4)
    assert result[0].confidence == expected


def test_input_list_and_items_not_mutated() -> None:
    segments = [
        seg(0, 1000, "First."),
        seg(1000, 1200, "Short."),
        seg(1200, 2500, "Last."),
    ]
    original_copy = [s.model_copy() for s in segments]

    merge_short_segments(segments, min_duration_ms=500)

    assert segments == original_copy


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_duration_ms": -1},
        {"max_gap_ms": -1},
        {"max_merged_duration_ms": 0},
        {"max_merged_duration_ms": -100},
    ],
)
def test_invalid_args_raise_value_error(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        merge_short_segments([seg(0, 1000, "Hello.")], **kwargs)
