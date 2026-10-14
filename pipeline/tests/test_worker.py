import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from dubforge_contracts.models import (
    Artifact,
    ArtifactQueueMessage,
    ArtifactStatus,
    AudioResult,
    ExportJobQueueMessage,
    ExportKind,
    JobQueueMessage,
    Segment,
)
from dubforge_pipeline import worker
from dubforge_pipeline.providers.base import TTSProvider


class _FakeTTSProvider(TTSProvider):
    def __init__(self, source_path: str) -> None:
        self._source_path = source_path

    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        return AudioResult(audio_path=self._source_path, actual_duration_ms=2000)


class _RaisingTTSProvider(TTSProvider):
    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        raise RuntimeError("tts exploded")


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


def test_process_artifact_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    source_path = tmp_path / "source" / "fake_audio.wav"
    source_path.parent.mkdir()
    source_path.write_bytes(b"RIFF....WAVEfmt ")
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setattr(
        worker,
        "_get_tts_provider",
        lambda: _FakeTTSProvider(str(source_path)),
    )

    artifact_id = uuid.uuid4()
    message = ArtifactQueueMessage(artifact_id=artifact_id, segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(storage_root), message)

    statuses = _status_calls(calls)
    assert statuses == ["processing", "completed"]
    assert calls[-1]["audio_path"] == f"artifacts/{artifact_id}.wav"
    assert calls[-1]["duration_ms"] == 2000
    assert calls[-1]["voice_profile"] == "default"
    assert (storage_root / "artifacts" / f"{artifact_id}.wav").exists()
    assert not source_path.exists()


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


def test_process_artifact_reports_failure_when_audio_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        worker,
        "_get_tts_provider",
        lambda: _FakeTTSProvider(str(tmp_path / "does_not_exist.wav")),
    )

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "failed"
    assert "does not exist" in str(calls[-1]["error_message"])


def _segment_with_artifact(start_ms: int, audio_path: str | None) -> Segment:
    now = datetime.now(UTC)
    artifact = (
        Artifact(
            status=ArtifactStatus.COMPLETED,
            audio_path=audio_path,
            duration_ms=1000,
            created_at=now,
            updated_at=now,
        )
        if audio_path is not None
        else None
    )
    return Segment(
        index=0,
        start_ms=start_ms,
        end_ms=start_ms + 1000,
        duration_ms=1000,
        speaker_label="A",
        text="Hi",
        artifact=artifact,
    )


def _client_with_segments(segments: list[Segment], calls: list[Any]) -> httpx.Client:
    segments_json = [s.model_dump(mode="json") for s in segments]

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        if request.method == "GET":
            return httpx.Response(200, json=segments_json)
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_process_export_job_mp3_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    storage_root = tmp_path
    audio_path = storage_root / "artifacts" / "seg0.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"fake")
    (storage_root / "proj").mkdir()
    (storage_root / "proj" / "video.mp4").write_bytes(b"fake video")

    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)
    build_calls: list[Any] = []

    def fake_build(segment_audio: Any, total_duration_ms: Any, output_wav_path: str) -> str:
        build_calls.append((segment_audio, total_duration_ms, output_wav_path))
        return output_wav_path

    monkeypatch.setattr(worker, "build_dub_audio_track", fake_build)

    encode_calls: list[Any] = []

    def fake_encode_mp3(wav: str, out: str) -> str:
        encode_calls.append((wav, out))
        return out

    monkeypatch.setattr(worker, "encode_mp3", fake_encode_mp3)

    def fail_mux(*_a: object, **_k: object) -> str:
        raise AssertionError("should not run")

    monkeypatch.setattr(worker, "mux_mp4", fail_mux)

    export_job_id = uuid.uuid4()
    message = ExportJobQueueMessage(
        export_job_id=export_job_id,
        media_id=uuid.uuid4(),
        kind=ExportKind.MP3,
        media_storage_path="proj/video.mp4",
    )
    segments = [_segment_with_artifact(0, "artifacts/seg0.wav")]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(storage_root), message)

    statuses = _status_calls(calls)
    assert statuses == ["processing", "processing", "processing", "processing", "completed"]
    assert calls[-1]["progress"] == 100
    assert calls[-1]["output_path"] == f"exports/{export_job_id}.mp3"
    assert len(encode_calls) == 1
    assert len(build_calls) == 1


def test_process_export_job_mp4_dispatches_to_mux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    storage_root = tmp_path
    audio_path = storage_root / "artifacts" / "seg0.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"fake")
    (storage_root / "proj").mkdir()
    (storage_root / "proj" / "video.mp4").write_bytes(b"fake video")

    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)
    monkeypatch.setattr(
        worker, "build_dub_audio_track", lambda _segs, _total_ms, output_wav_path: output_wav_path
    )

    def fail_encode(*_a: object, **_k: object) -> str:
        raise AssertionError("should not run")

    monkeypatch.setattr(worker, "encode_mp3", fail_encode)

    mux_calls: list[Any] = []

    def fake_mux(video: str, wav: str, out: str) -> str:
        mux_calls.append((video, wav, out))
        return out

    monkeypatch.setattr(worker, "mux_mp4", fake_mux)

    export_job_id = uuid.uuid4()
    message = ExportJobQueueMessage(
        export_job_id=export_job_id,
        media_id=uuid.uuid4(),
        kind=ExportKind.MP4,
        media_storage_path="proj/video.mp4",
    )
    segments = [_segment_with_artifact(0, "artifacts/seg0.wav")]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(storage_root), message)

    assert calls[-1]["status"] == "completed"
    assert calls[-1]["output_path"] == f"exports/{export_job_id}.mp4"
    assert len(mux_calls) == 1


def test_process_export_job_fails_when_segment_has_no_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "video.mp4").write_bytes(b"fake video")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)

    message = ExportJobQueueMessage(
        export_job_id=uuid.uuid4(),
        media_id=uuid.uuid4(),
        kind=ExportKind.MP3,
        media_storage_path="proj/video.mp4",
    )
    segments = [_segment_with_artifact(0, None)]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "failed"
    assert "no usable audio artifact" in str(calls[-1]["error_message"])


def test_process_export_job_fails_when_audio_file_missing_on_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "video.mp4").write_bytes(b"fake video")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)

    message = ExportJobQueueMessage(
        export_job_id=uuid.uuid4(),
        media_id=uuid.uuid4(),
        kind=ExportKind.MP3,
        media_storage_path="proj/video.mp4",
    )
    segments = [_segment_with_artifact(0, "artifacts/does_not_exist.wav")]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "failed"
    assert "missing on disk" in str(calls[-1]["error_message"])
