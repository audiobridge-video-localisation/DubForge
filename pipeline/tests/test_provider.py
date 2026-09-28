from dubforge_pipeline.providers.mock import MockSTTProvider


def test_mock_stt_returns_segments() -> None:
    provider = MockSTTProvider()
    segments = provider.transcribe("fake_path.wav")
    assert len(segments) == 2
    assert segments[0].text == "Hello, this is a test."