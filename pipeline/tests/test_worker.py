import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from dubforge_contracts.models import JobQueueMessage, Segment
from dubforge_pipeline import worker


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
    assert segment_calls[0][0]["translated_text"] == "[es] Hi"


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
