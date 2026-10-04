import json
import uuid
from pathlib import Path

import httpx
import pytest

from dubforge_contracts.models import JobQueueMessage
from dubforge_pipeline import worker


def _client_recording(calls: list[dict[str, object]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_process_job_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(worker, "extract_audio", lambda *_args, **_kwargs: "out.wav")

    message = JobQueueMessage(
        job_id=uuid.uuid4(), media_id=uuid.uuid4(), storage_path="proj/video.mp4"
    )
    with _client_recording(calls) as client:
        worker.process_job(client, "http://api", str(tmp_path), message)

    statuses = [call["status"] for call in calls]
    assert statuses == ["processing", "processing", "processing", "completed"]
    assert calls[-1]["progress"] == 100


def test_process_job_reports_failure_on_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []

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
