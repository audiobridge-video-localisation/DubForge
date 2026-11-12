from dubforge_contracts.export import segments_to_srt, segments_to_vtt
from dubforge_contracts.models import TranscriptSegment


def test_segments_to_srt_smoke() -> None:
    segments = [TranscriptSegment(start_ms=0, end_ms=1000, text="Hello")]
    body = segments_to_srt(segments)
    assert "00:00:00,000 --> 00:00:01,000" in body
    assert "Hello" in body


def test_segments_to_vtt_smoke() -> None:
    segments = [TranscriptSegment(start_ms=0, end_ms=1000, text="Hello")]
    body = segments_to_vtt(segments)
    assert body.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in body
