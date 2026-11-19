import pytest

from dubforge_contracts.models import TranscriptSegment
from dubforge_pipeline.export import (
    format_srt_timestamp,
    format_vtt_timestamp,
    segments_to_srt,
    segments_to_vtt,
)


def seg(start_ms: int, end_ms: int, text: str) -> TranscriptSegment:
    return TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text)


@pytest.mark.parametrize(
    ("ms", "expected_srt", "expected_vtt"),
    [
        (0, "00:00:00,000", "00:00:00.000"),
        (999, "00:00:00,999", "00:00:00.999"),
        (1000, "00:00:01,000", "00:00:01.000"),
        (61_001, "00:01:01,001", "00:01:01.001"),
        (3_600_000, "01:00:00,000", "01:00:00.000"),
        (360_000_000, "100:00:00,000", "100:00:00.000"),
    ],
)
def test_format_timestamp(ms: int, expected_srt: str, expected_vtt: str) -> None:
    assert format_srt_timestamp(ms) == expected_srt
    assert format_vtt_timestamp(ms) == expected_vtt


def test_format_timestamp_negative_raises() -> None:
    with pytest.raises(ValueError):
        format_srt_timestamp(-1)
    with pytest.raises(ValueError):
        format_vtt_timestamp(-1)


def test_segments_to_srt_basic_two_segments() -> None:
    segments = [
        seg(0, 1000, "Hello there."),
        seg(1000, 2500, "This is a test."),
    ]
    expected = (
        "1\n00:00:00,000 --> 00:00:01,000\nHello there.\n\n"
        "2\n00:00:01,000 --> 00:00:02,500\nThis is a test.\n\n"
    )
    assert segments_to_srt(segments) == expected


def test_segments_to_vtt_basic_two_segments() -> None:
    segments = [
        seg(0, 1000, "Hello there."),
        seg(1000, 2500, "This is a test."),
    ]
    expected = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\nHello there.\n\n"
        "00:00:01.000 --> 00:00:02.500\nThis is a test.\n\n"
    )
    assert segments_to_vtt(segments) == expected


def test_segments_to_srt_empty_list() -> None:
    assert segments_to_srt([]) == ""


def test_segments_to_vtt_empty_list() -> None:
    assert segments_to_vtt([]) == "WEBVTT\n\n"


def test_unsorted_input_comes_out_sorted() -> None:
    segments = [
        seg(2000, 3000, "Second."),
        seg(0, 1000, "First."),
    ]
    result = segments_to_srt(segments)
    assert result.index("First.") < result.index("Second.")
    assert result.startswith("1\n00:00:00,000 --> 00:00:01,000\nFirst.")


def test_input_list_not_mutated() -> None:
    segments = [
        seg(2000, 3000, "Second."),
        seg(0, 1000, "First."),
    ]
    original_order = list(segments)
    original_copies = [s.model_copy() for s in segments]

    segments_to_srt(segments)

    assert segments == original_order
    assert segments == original_copies


def test_empty_and_whitespace_text_segments_skipped() -> None:
    segments = [
        seg(0, 1000, "First."),
        seg(1000, 2000, "   "),
        seg(2000, 3000, ""),
        seg(3000, 4000, "Last."),
    ]
    result = segments_to_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:01,000\nFirst.\n\n" in result
    assert "2\n00:00:03,000 --> 00:00:04,000\nLast.\n\n" in result
    assert result.count("\n\n") == 2


def test_zero_and_negative_duration_segments_skipped() -> None:
    segments = [
        seg(0, 1000, "First."),
        seg(1000, 1000, "Zero duration."),
        seg(2000, 1500, "Negative duration."),
        seg(3000, 4000, "Last."),
    ]
    result = segments_to_srt(segments)
    assert "Zero duration." not in result
    assert "Negative duration." not in result
    assert result.startswith("1\n")
    assert "2\n00:00:03,000 --> 00:00:04,000\nLast.\n\n" in result


def test_srt_numbering_has_no_gaps_after_skipping() -> None:
    segments = [
        seg(0, 1000, "A"),
        seg(1000, 1000, ""),
        seg(2000, 3000, "B"),
        seg(3000, 3000, ""),
        seg(4000, 5000, "C"),
    ]
    result = segments_to_srt(segments)
    assert "1\n" in result
    assert "2\n" in result
    assert "3\n" in result
    assert "4\n" not in result


def test_multiline_text_crlf_normalisation_and_blank_line_collapse() -> None:
    segments = [seg(0, 1000, "Line one\r\n\r\n\r\nLine two\r")]
    result = segments_to_srt(segments)
    assert result == "1\n00:00:00,000 --> 00:00:01,000\nLine one\nLine two\n\n"


def test_vtt_escapes_ampersand_lt_gt() -> None:
    segments = [seg(0, 1000, "A & B < C > D")]
    result = segments_to_vtt(segments)
    assert "A &amp; B &lt; C &gt; D" in result


def test_srt_does_not_escape_special_characters() -> None:
    segments = [seg(0, 1000, "A & B < C > D")]
    result = segments_to_srt(segments)
    assert "A & B < C > D" in result


def test_non_ascii_text_passes_through_unchanged() -> None:
    hindi_text = "नमस्ते, यह एक परीक्षण है।"
    bengali_text = "নমস্কার, এটি একটি পরীক্ষা।"
    segments = [
        seg(0, 1000, hindi_text),
        seg(1000, 2000, bengali_text),
    ]
    srt_result = segments_to_srt(segments)
    vtt_result = segments_to_vtt(segments)
    assert hindi_text in srt_result
    assert bengali_text in srt_result
    assert hindi_text in vtt_result
    assert bengali_text in vtt_result
