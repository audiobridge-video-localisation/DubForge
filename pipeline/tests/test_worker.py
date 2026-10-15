import json
import logging
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from dubforge_contracts.models import (
    ArtifactQueueMessage,
    AudioResult,
    JobQueueMessage,
    Segment,
    TranscriptSegment,
)
from dubforge_pipeline import worker
from dubforge_pipeline.providers.base import TTSProvider
from dubforge_pipeline.providers.mock import MockTranslationProvider, MockTTSProvider


class _FakeTTSProvider(TTSProvider):
    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        return AudioResult(audio_path="/tmp/fake_audio.wav", actual_duration_ms=2000)


class _RaisingTTSProvider(TTSProvider):
    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        raise RuntimeError("tts exploded")


@pytest.fixture(autouse=True)
def _reset_worker_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    worker.reset_provider_cache()
    monkeypatch.delenv("TARGET_LANGS", raising=False)
    monkeypatch.delenv("SOURCE_LANG", raising=False)
    monkeypatch.delenv("MIN_SEGMENT_MS", raising=False)
    yield
    worker.reset_provider_cache()


def _client_recording(calls: list[Any]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _patch_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "extract_audio", lambda *_args, **_kwargs: "out.wav")
    monkeypatch.setattr(
        worker,
        "_get_transcription",
        lambda *_args, **_kwargs: ([], []),
    )


def _status_calls(calls: list[Any]) -> list[str]:
    return [call["status"] for call in calls if isinstance(call, dict)]


def test_process_job_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _patch_transcription(monkeypatch)

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    statuses = _status_calls(calls)
    assert statuses == ["processing", "processing", "processing", "processing", "completed"]
    assert calls[-1]["progress"] == 100


def test_process_job_submits_segments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "extract_audio", lambda *_args, **_kwargs: "out.wav")
    monkeypatch.setattr(
        worker,
        "_get_transcription",
        lambda *_args, **_kwargs: (
            [],
            [],
        ),
    )
    expected_segments = [
        Segment(index=0, start_ms=0, end_ms=1000, duration_ms=1000, speaker_label="A", text="Hi")
    ]
    monkeypatch.setattr(worker, "combine_segments", lambda *_args, **_kwargs: expected_segments)

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    segment_calls = [call for call in calls if isinstance(call, list)]
    assert len(segment_calls) == 1
    assert segment_calls[0][0]["text"] == "Hi"
    assert segment_calls[0][0]["speaker_label"] == "A"
    # Default TARGET_LANGS is "hi" (was hardcoded "es" before real
    # translation providers were wired in).
    assert segment_calls[0][0]["translated_text"] == "[hi] Hi"


def test_process_job_reports_failure_on_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []

    def _raise(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(worker, "extract_audio", _raise)

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "failed"
    assert "ffmpeg exploded" in str(calls[-1]["error_message"])


def test_process_job_merges_short_segments_before_combine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "extract_audio", lambda *_args, **_kwargs: "out.wav")

    short_segments = [
        TranscriptSegment(start_ms=0, end_ms=200, text="Hi"),
        TranscriptSegment(start_ms=200, end_ms=400, text="there"),
    ]
    monkeypatch.setattr(worker, "_get_transcription", lambda *_a, **_k: (short_segments, []))

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    segment_calls = [call for call in calls if isinstance(call, list)]
    assert len(segment_calls) == 1
    # Both segments are under the 500ms default and adjacent, so
    # merge_short_segments collapses them into one before combine_segments.
    assert len(segment_calls[0]) == 1
    assert segment_calls[0][0]["text"] == "Hi there"


def test_process_job_min_segment_ms_env_is_respected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "extract_audio", lambda *_args, **_kwargs: "out.wav")
    monkeypatch.setenv("MIN_SEGMENT_MS", "0")

    short_segments = [
        TranscriptSegment(start_ms=0, end_ms=200, text="Hi"),
        TranscriptSegment(start_ms=200, end_ms=400, text="there"),
    ]
    monkeypatch.setattr(worker, "_get_transcription", lambda *_a, **_k: (short_segments, []))

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    segment_calls = [call for call in calls if isinstance(call, list)]
    # MIN_SEGMENT_MS=0 means neither 200ms segment counts as "short", so
    # they stay separate instead of merging.
    assert len(segment_calls[0]) == 2


def test_translator_provider_cached_across_two_jobs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _patch_transcription(monkeypatch)

    call_count = 0

    def _factory() -> MockTranslationProvider:
        nonlocal call_count
        call_count += 1
        return MockTranslationProvider()

    monkeypatch.setattr(worker, "get_translation_provider", _factory)

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)
        worker.process_job(client, "http://api", str(tmp_path), message)

    assert call_count == 1


def test_tts_provider_cached_across_two_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    call_count = 0

    def _factory() -> MockTTSProvider:
        nonlocal call_count
        call_count += 1
        return MockTTSProvider()

    monkeypatch.setattr(worker, "get_tts_provider", _factory)

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert call_count == 1


def test_get_target_lang_default_is_hi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_LANGS", raising=False)
    assert worker._get_target_lang() == "hi"


def test_get_target_lang_uses_first_of_many_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("TARGET_LANGS", "hi,bn,ta")
    with caplog.at_level(logging.WARNING, logger="dubforge_pipeline.worker"):
        result = worker._get_target_lang()

    assert result == "hi"
    assert "TARGET_LANGS" in caplog.text
    assert "hi" in caplog.text


def test_process_artifact_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        worker,
        "_get_tts_provider",
        lambda: _FakeTTSProvider(),
    )

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    statuses = _status_calls(calls)
    assert statuses == ["processing", "completed"]
    # _FakeTTSProvider's path ("/tmp/fake_audio.wav") is never actually
    # written, so there's nothing to copy and the original path is reported
    # unchanged - matches the mock-provider offline/deterministic behavior.
    assert calls[-1]["audio_path"] == "/tmp/fake_audio.wav"
    assert calls[-1]["duration_ms"] == 2000


def test_process_artifact_reports_failure_on_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _RaisingTTSProvider())

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "failed"
    assert "tts exploded" in str(calls[-1]["error_message"])


def test_process_artifact_uses_target_lang_as_voice_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    received_voice_profiles: list[str] = []

    class _RecordingTTSProvider(TTSProvider):
        def synthesize(
            self, text: str, voice_profile: str, target_duration_ms: int | None = None
        ) -> AudioResult:
            received_voice_profiles.append(voice_profile)
            return AudioResult(audio_path="/tmp/fake_audio.wav", actual_duration_ms=2000)

    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _RecordingTTSProvider())
    monkeypatch.setenv("TARGET_LANGS", "bn")

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert received_voice_profiles == ["bn"]


def test_process_artifact_empty_text_fails_without_calling_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    provider_called = False

    class _ShouldNotBeCalledTTSProvider(TTSProvider):
        def synthesize(
            self, text: str, voice_profile: str, target_duration_ms: int | None = None
        ) -> AudioResult:
            nonlocal provider_called
            provider_called = True
            return AudioResult(audio_path="/tmp/fake_audio.wav", actual_duration_ms=2000)

    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _ShouldNotBeCalledTTSProvider())

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="   ")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert provider_called is False
    assert calls[-1]["status"] == "failed"
    assert calls[-1]["error_message"] == "empty text"


def test_process_artifact_copies_audio_into_storage_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    source_path = tmp_path / "elsewhere" / "speech.wav"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"fake wav bytes")

    class _RealFileTTSProvider(TTSProvider):
        def synthesize(
            self, text: str, voice_profile: str, target_duration_ms: int | None = None
        ) -> AudioResult:
            return AudioResult(audio_path=str(source_path), actual_duration_ms=1500)

    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _RealFileTTSProvider())

    storage_dir = tmp_path / "storage"
    artifact_id = uuid.uuid4()
    message = ArtifactQueueMessage(artifact_id=artifact_id, segment_id=uuid.uuid4(), text="Hello")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(storage_dir), message)

    expected_path = storage_dir / "artifacts" / f"{artifact_id}.wav"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"fake wav bytes"
    assert calls[-1]["audio_path"] == str(expected_path)
    assert calls[-1]["duration_ms"] == 1500
