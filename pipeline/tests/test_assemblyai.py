from pathlib import Path

import httpx
import pytest

from dubforge_pipeline.providers import assemblyai


def _audio_file(tmp_path: Path) -> str:
    path = tmp_path / "audio.wav"
    path.write_bytes(b"fake audio bytes")
    return str(path)


def _mock_client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_transcribe_with_diarization_happy_path(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/upload":
            return httpx.Response(200, json={"upload_url": "https://cdn/upload/abc"})
        if request.url.path == "/v2/transcript" and request.method == "POST":
            return httpx.Response(200, json={"id": "transcript-1", "status": "queued"})
        if request.url.path == "/v2/transcript/transcript-1":
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "utterances": [
                        {"start": 0, "end": 2000, "text": "Hello", "speaker": "A"},
                        {"start": 2000, "end": 4000, "text": "World", "speaker": "B"},
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    with _mock_client(httpx.MockTransport(handler)) as client:
        transcripts, speakers = assemblyai.transcribe_with_diarization(
            _audio_file(tmp_path), api_key="key", poll_interval_s=0, client=client
        )

    assert [t.text for t in transcripts] == ["Hello", "World"]
    assert [s.speaker_label for s in speakers] == ["Speaker A", "Speaker B"]
    assert transcripts[0].start_ms == 0
    assert transcripts[0].end_ms == 2000


def test_transcribe_with_diarization_raises_on_error_status(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/upload":
            return httpx.Response(200, json={"upload_url": "https://cdn/upload/abc"})
        if request.url.path == "/v2/transcript" and request.method == "POST":
            return httpx.Response(200, json={"id": "transcript-1", "status": "queued"})
        return httpx.Response(200, json={"status": "error", "error": "bad audio"})

    with (
        _mock_client(httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="bad audio"),
    ):
        assemblyai.transcribe_with_diarization(
            _audio_file(tmp_path), api_key="key", poll_interval_s=0, client=client
        )


def test_transcribe_with_diarization_raises_on_timeout(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/upload":
            return httpx.Response(200, json={"upload_url": "https://cdn/upload/abc"})
        if request.url.path == "/v2/transcript" and request.method == "POST":
            return httpx.Response(200, json={"id": "transcript-1", "status": "queued"})
        return httpx.Response(200, json={"status": "queued"})

    with (
        _mock_client(httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="timed out"),
    ):
        assemblyai.transcribe_with_diarization(
            _audio_file(tmp_path),
            api_key="key",
            poll_interval_s=0,
            timeout_s=0,
            client=client,
        )
