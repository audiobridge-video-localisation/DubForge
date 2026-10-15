from dubforge_pipeline.providers.mock import MockSTTProvider, MockTTSProvider


def test_mock_stt_returns_segments() -> None:
    provider = MockSTTProvider()
    segments = provider.transcribe("fake_path.wav")
    assert len(segments) == 2
    assert segments[0].text == "Hello, this is a test."


def test_mock_tts_returns_default_duration() -> None:
    provider = MockTTSProvider()
    result = provider.synthesize("Hello", "voice_1")
    assert result.actual_duration_ms == 2000


def test_mock_tts_returns_target_duration() -> None:
    provider = MockTTSProvider()
    result = provider.synthesize("Hello", "voice_1", target_duration_ms=3500)
    assert result.actual_duration_ms == 3500
