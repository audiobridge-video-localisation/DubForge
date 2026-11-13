import json
import uuid
from collections.abc import Iterator
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
    TranscriptSegment,
)
from dubforge_pipeline import worker
from dubforge_pipeline.providers.base import TTSProvider
from dubforge_pipeline.providers.mock import MockTranslationProvider, MockTTSProvider


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
    # JobQueueMessage.target_lang defaults to "hi" (was hardcoded "es" before real
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
    # voice_profile now reflects the configured target language (default "hi"),
    # not a hardcoded placeholder - see test_process_artifact_uses_target_lang_as_voice_profile.
    assert calls[-1]["voice_profile"] == "hi"
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


def test_process_artifact_uses_target_lang_as_voice_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    received_voice_profiles: list[str] = []
    source_path = tmp_path / "speech.wav"
    source_path.write_bytes(b"fake wav bytes")

    class _RecordingTTSProvider(TTSProvider):
        def synthesize(
            self, text: str, voice_profile: str, target_duration_ms: int | None = None
        ) -> AudioResult:
            received_voice_profiles.append(voice_profile)
            return AudioResult(audio_path=str(source_path), actual_duration_ms=2000)

    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _RecordingTTSProvider())

    message = ArtifactQueueMessage(
        artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola", target_lang="bn"
    )
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(tmp_path), message)

    assert received_voice_profiles == ["bn"]
    assert calls[-1]["voice_profile"] == "bn"


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


def test_process_artifact_persists_audio_into_storage_dir(
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
    assert not source_path.exists()
    # Reported relative to storage_root, mirroring Media.storage_path's convention.
    assert calls[-1]["audio_path"] == f"artifacts/{artifact_id}.wav"
    assert calls[-1]["duration_ms"] == 1500


@pytest.fixture(autouse=True)
def _no_background(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exports here carry the dub alone unless a test gives them a background."""
    monkeypatch.setattr(worker, "separate_background", lambda _video: None)


@pytest.fixture(autouse=True)
def _no_silence_trimming(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake audio files in these tests are not real WAVs; exports use them as they are."""

    def _cannot_trim(*_a: object, **_k: object) -> str:
        raise RuntimeError("not a real clip")

    monkeypatch.setattr(worker, "trim_silence", _cannot_trim)


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

    def fake_mux(video: str, wav: str, out: str, **kwargs: Any) -> str:
        mux_calls.append((video, wav, out, kwargs))
        return out

    def fail_rebuild(*_a: object, **_k: object) -> str:
        raise AssertionError("a fitting dub must not re-encode the video")

    monkeypatch.setattr(worker, "build_timeline_video", fail_rebuild)

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
    video, _wav, _out, kwargs = mux_calls[0]
    assert video == str(storage_root / "proj" / "video.mp4")  # the original, untouched
    assert kwargs["subtitles_path"].endswith("dub.srt")
    # default target_lang is "hi"
    assert kwargs["subtitle_language"] == "hin"


def test_process_export_job_mp4_uses_the_media_target_lang_for_subtitles(
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
    monkeypatch.setattr(worker, "build_timeline_video", lambda *_a, **_k: None)

    mux_calls: list[Any] = []

    def fake_mux(video: str, wav: str, out: str, **kwargs: Any) -> str:
        mux_calls.append((video, wav, out, kwargs))
        return out

    monkeypatch.setattr(worker, "mux_mp4", fake_mux)

    message = ExportJobQueueMessage(
        export_job_id=uuid.uuid4(),
        media_id=uuid.uuid4(),
        kind=ExportKind.MP4,
        media_storage_path="proj/video.mp4",
        target_lang="bn",
    )
    segments = [_segment_with_artifact(0, "artifacts/seg0.wav")]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(storage_root), message)

    assert calls[-1]["status"] == "completed"
    assert mux_calls[0][3]["subtitle_language"] == "ben"


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


def _segment_with_audio_duration(
    start_ms: int, end_ms: int, audio_path: str, audio_duration_ms: int | None
) -> Segment:
    now = datetime.now(UTC)
    return Segment(
        index=0,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        speaker_label="A",
        text="Hi",
        artifact=Artifact(
            status=ArtifactStatus.COMPLETED,
            audio_path=audio_path,
            duration_ms=audio_duration_ms,
            created_at=now,
            updated_at=now,
        ),
    )


def _export_message() -> ExportJobQueueMessage:
    return ExportJobQueueMessage(
        export_job_id=uuid.uuid4(),
        media_id=uuid.uuid4(),
        kind=ExportKind.MP3,
        media_storage_path="proj/video.mp4",
    )


def _prepare_export_storage(storage_root: Path, *audio_names: str) -> None:
    (storage_root / "artifacts").mkdir(parents=True)
    for name in audio_names:
        (storage_root / "artifacts" / name).write_bytes(b"fake")
    (storage_root / "proj").mkdir()
    (storage_root / "proj" / "video.mp4").write_bytes(b"fake video")


def test_process_export_job_speeds_up_overrunning_segment_and_places_next_later(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav", "seg1.wav")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)

    tempo_calls: list[tuple[str, str, float]] = []

    def fake_apply_tempo(input_path: str, output_path: str, tempo: float) -> str:
        tempo_calls.append((input_path, output_path, tempo))
        return output_path

    monkeypatch.setattr(worker, "apply_tempo", fake_apply_tempo)

    build_calls: list[Any] = []

    def fake_build(segment_audio: Any, total_duration_ms: Any, output_wav_path: str) -> str:
        build_calls.append((segment_audio, total_duration_ms))
        return output_wav_path

    monkeypatch.setattr(worker, "build_dub_audio_track", fake_build)
    monkeypatch.setattr(worker, "encode_mp3", lambda _wav, out: out)

    # seg0: 1200ms of audio in a 1000ms room -> 1.2x. seg1 fits and keeps its start.
    segments = [
        _segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 1200),
        _segment_with_audio_duration(1000, 2000, "artifacts/seg1.wav", 500),
    ]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    # seg0 is sped up to fit; seg1 (500ms for a 1000ms line) is slowed a little to fill it
    assert [(path.rsplit("/", 1)[-1], tempo) for path, _out, tempo in tempo_calls] == [
        ("seg0.wav", pytest.approx(1.2)),
        ("seg1.wav", pytest.approx(0.85)),
    ]

    placed, total_ms = build_calls[0]
    assert total_ms == 5000
    assert placed[0] == (0, tempo_calls[0][1])
    assert placed[1] == (1000, tempo_calls[1][1])


def test_process_export_job_gives_a_long_line_the_time_it_needs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav", "seg1.wav")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 10_000)
    monkeypatch.setattr(worker, "apply_tempo", lambda _in, out, _tempo: out)

    build_calls: list[Any] = []

    def fake_build(segment_audio: Any, total_duration_ms: Any, output_wav_path: str) -> str:
        build_calls.append(segment_audio)
        return output_wav_path

    monkeypatch.setattr(worker, "build_dub_audio_track", fake_build)
    monkeypatch.setattr(worker, "encode_mp3", lambda _wav, out: out)

    # 3000ms in a 1000ms room: 1.25x speech plays 2400ms; the export timeline makes the
    # window that long (slower video, then a held frame), so seg1 starts at 2400.
    segments = [
        _segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 3000),
        _segment_with_audio_duration(1000, 2000, "artifacts/seg1.wav", 500),
    ]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    assert [start for start, _path in build_calls[0]] == [0, 2400]


@pytest.mark.parametrize("recorded_duration", [None, 0])
def test_process_export_job_probes_audio_when_artifact_duration_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recorded_duration: int | None
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav")
    audio_abs_path = str(tmp_path / "artifacts" / "seg0.wav")

    probed: list[str] = []

    def fake_probe(path: str, *_a: object, **_k: object) -> int:
        probed.append(path)
        return 5000 if path.endswith("video.mp4") else 1500

    monkeypatch.setattr(worker, "probe_duration_ms", fake_probe)
    monkeypatch.setattr(worker, "apply_tempo", lambda _in, out, _tempo: out)
    monkeypatch.setattr(worker, "build_dub_audio_track", lambda _s, _t, out: out)
    monkeypatch.setattr(worker, "encode_mp3", lambda _wav, out: out)

    segments = [_segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", recorded_duration)]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    assert audio_abs_path in probed


def test_process_artifact_learns_the_voice_speed_from_real_takes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dubforge_pipeline.speech_rate import get_ms_per_char

    class _RealVoice(TTSProvider):
        def synthesize(
            self, text: str, voice_profile: str, target_duration_ms: int | None = None
        ) -> AudioResult:
            path = tmp_path / "take.wav"
            path.write_bytes(b"RIFF....WAVEfmt ")
            # 10 chars in 500 ms, spoken 1.25x faster than natural: 62.5 ms per char naturally
            return AudioResult(audio_path=str(path), actual_duration_ms=500, speech_rate=1.25)

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _RealVoice())

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="x" * 10)
    calls: list[Any] = []
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(storage_root), message)

    assert get_ms_per_char(str(storage_root), worker._voice_key("hi")) == pytest.approx(62.5)
    # export may only speed it up by what is left of MAX_SPEEDUP
    assert calls[-1]["speedup"] == pytest.approx(1.25)


def test_process_artifact_does_not_learn_from_the_mock_voice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dubforge_pipeline.speech_rate import DEFAULT_MS_PER_CHAR, get_ms_per_char

    source_path = tmp_path / "fake.wav"
    source_path.write_bytes(b"RIFF....WAVEfmt ")
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setattr(worker, "_get_tts_provider", lambda: _FakeTTSProvider(str(source_path)))

    message = ArtifactQueueMessage(artifact_id=uuid.uuid4(), segment_id=uuid.uuid4(), text="Hola")
    with _client_recording([]) as client:
        worker.process_artifact(client, "http://api", str(storage_root), message)

    assert get_ms_per_char(str(storage_root), worker._voice_key("hi")) == DEFAULT_MS_PER_CHAR


# --- shortening a line that still does not fit -------------------------------------------


class _LengthVoice(TTSProvider):
    """Says every character in 100 ms, never faster, and records what it was asked to say."""

    def __init__(self, take_dir: Path) -> None:
        self.take_dir = take_dir
        self.said: list[str] = []

    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        import wave

        self.said.append(text)
        duration_ms = len(text) * 100
        self.take_dir.mkdir(exist_ok=True)
        path = self.take_dir / f"take{len(self.said)}.wav"
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(1000)
            wav_file.writeframes(b"\x00\x00" * duration_ms)
        return AudioResult(audio_path=str(path), actual_duration_ms=duration_ms, speech_rate=1.0)


class _Alternatives(MockTranslationProvider):
    def __init__(self, candidates: list[str] | Exception) -> None:
        self.candidates = candidates
        self.asked = 0

    def translate_candidates(
        self, text: str, src_lang: str, tgt_lang: str, count: int = 1
    ) -> list[str]:
        self.asked += 1
        if isinstance(self.candidates, Exception):
            raise self.candidates
        return self.candidates


def _run_shortening(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    voice: _LengthVoice,
    translator: _Alternatives,
    text: str,
    room_ms: int = 1000,
    may_rewrite: bool = True,
) -> list[Any]:
    calls: list[Any] = []
    storage_root = tmp_path / "storage"
    storage_root.mkdir(exist_ok=True)
    monkeypatch.setattr(worker, "_get_tts_provider", lambda: voice)
    monkeypatch.setattr(worker, "_get_translator", lambda: translator)
    message = ArtifactQueueMessage(
        artifact_id=uuid.uuid4(),
        segment_id=uuid.uuid4(),
        text=text,
        target_duration_ms=room_ms,
        source_text="the source line",
        may_rewrite=may_rewrite,
    )
    with _client_recording(calls) as client:
        worker.process_artifact(client, "http://api", str(storage_root), message)
    return calls


def test_a_line_that_is_too_long_is_shortened_automatically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(["x" * 40, "y" * 12, "z" * 8])

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 40)

    assert _status_calls(calls) == ["processing", "completed"]
    assert voice.said == ["x" * 40, "y" * 12]  # the long wording, then the first that fits
    assert calls[-1]["translated_text"] == "y" * 12
    assert calls[-1]["duration_ms"] == 1200  # within the room (1000 ms + 300 ms)
    assert list((tmp_path / "takes").iterdir()) == []  # rejected and persisted takes are gone


def test_a_line_that_already_fits_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(["a" * 5])

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 10)

    assert translator.asked == 0
    assert voice.said == ["x" * 10]
    assert "translated_text" not in calls[-1]


def test_a_line_a_person_edited_is_never_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(["y" * 12])

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 40, may_rewrite=False)

    assert translator.asked == 0
    assert voice.said == ["x" * 40]
    assert calls[-1]["duration_ms"] == 4000 and "translated_text" not in calls[-1]


def test_when_no_wording_fits_the_shortest_take_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(["x" * 40, "y" * 30, "z" * 35])

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 40)

    assert calls[-1]["translated_text"] == "y" * 30  # 3000 ms still too long, but the best
    assert calls[-1]["duration_ms"] == 3000
    assert list((tmp_path / "takes").iterdir()) == []


def test_when_no_alternative_is_shorter_the_original_stands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(["x" * 40, "w" * 38])  # not clearly shorter

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 40)

    assert voice.said == ["x" * 40]
    assert calls[-1]["duration_ms"] == 4000 and "translated_text" not in calls[-1]


def test_a_failing_translator_does_not_fail_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    voice = _LengthVoice(tmp_path / "takes")
    translator = _Alternatives(RuntimeError("model unavailable"))

    calls = _run_shortening(monkeypatch, tmp_path, voice, translator, "x" * 40)

    assert _status_calls(calls) == ["processing", "completed"]
    assert calls[-1]["duration_ms"] == 4000 and "translated_text" not in calls[-1]


def test_process_export_job_mp4_slows_the_video_for_a_line_speech_alone_cannot_fit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav", "seg1.wav")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)
    monkeypatch.setattr(worker, "apply_tempo", lambda _in, out, _tempo: out)
    totals: list[int] = []
    monkeypatch.setattr(
        worker, "build_dub_audio_track", lambda _s, total, out: totals.append(total) or out
    )
    rebuilt: list[Any] = []

    def fake_rebuild(video: str, pieces: Any, _work: str, out: str) -> str:
        rebuilt.append(pieces)
        return out

    monkeypatch.setattr(worker, "build_timeline_video", fake_rebuild)
    muxed: list[str] = []
    monkeypatch.setattr(
        worker, "mux_mp4", lambda video, _wav, out, **_k: muxed.append(video) or out
    )

    # 1500ms in a 1000ms room: speech and video each take about 1.22x
    segments = [
        _segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 1500),
        _segment_with_audio_duration(1000, 2000, "artifacts/seg1.wav", 500),
    ]
    message = _export_message().model_copy(update={"kind": ExportKind.MP4})
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), message)

    assert calls[-1]["status"] == "completed"
    assert rebuilt and rebuilt[0][0].slowdown == pytest.approx(1.5**0.5)
    assert muxed[0].endswith("timeline_video.mp4")
    assert totals == [5225]  # the dub track is as long as the re-timed video


def test_process_export_job_plans_with_the_trimmed_clip_length(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav")
    # a 1000ms video: the only line's room ends there
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 1000)
    monkeypatch.setattr(worker, "trim_silence", lambda _in, out: out)
    monkeypatch.setattr(worker, "wav_duration_ms", lambda _path: 1000)
    tempos: list[float] = []
    monkeypatch.setattr(worker, "apply_tempo", lambda _in, out, tempo: tempos.append(tempo) or out)
    placed: list[Any] = []
    monkeypatch.setattr(
        worker, "build_dub_audio_track", lambda segs, _t, out: placed.extend(segs) or out
    )
    monkeypatch.setattr(worker, "encode_mp3", lambda _wav, out: out)

    # recorded at 1200ms (too long for the 1000ms room), but 200ms of it was silence
    segments = [_segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 1200)]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    assert tempos == []  # it fits once trimmed, so no speed-up
    assert placed[0][1].endswith("segment_0_trim.wav")


def test_process_export_job_lays_the_dub_over_the_video_background(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)
    monkeypatch.setattr(worker, "build_dub_audio_track", lambda _s, _t, out: out)
    monkeypatch.setattr(worker, "separate_background", lambda _video: "/media/bg.wav")
    timed: list[Any] = []
    monkeypatch.setattr(
        worker,
        "build_timeline_background",
        lambda bg, pieces, out: timed.append((bg, pieces)) or out,
    )
    mixed: list[Any] = []
    monkeypatch.setattr(
        worker,
        "mix_with_background",
        lambda dub, bed, out, dub_gain_db=0.0: mixed.append((dub, bed, dub_gain_db)) or out,
    )
    encoded: list[str] = []
    monkeypatch.setattr(worker, "encode_mp3", lambda wav, out: encoded.append(wav) or out)

    segments = [_segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 1000)]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    assert timed[0][0] == "/media/bg.wav"
    assert mixed[0][0].endswith("dub_track.wav") and mixed[0][1].endswith("bed.wav")
    assert mixed[0][2] == 0.0  # no separated voice to match: the dub keeps its level
    assert encoded[0].endswith("soundtrack.wav")


def test_process_export_job_keeps_the_dub_alone_when_mixing_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    _prepare_export_storage(tmp_path, "seg0.wav")
    monkeypatch.setattr(worker, "probe_duration_ms", lambda *_a, **_k: 5000)
    monkeypatch.setattr(worker, "build_dub_audio_track", lambda _s, _t, out: out)
    monkeypatch.setattr(worker, "separate_background", lambda _video: "/media/bg.wav")

    def _broken(*_a: object, **_k: object) -> str:
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(worker, "build_timeline_background", _broken)
    encoded: list[str] = []
    monkeypatch.setattr(worker, "encode_mp3", lambda wav, out: encoded.append(wav) or out)

    segments = [_segment_with_audio_duration(0, 1000, "artifacts/seg0.wav", 1000)]
    with _client_with_segments(segments, calls) as client:
        worker.process_export_job(client, "http://api", str(tmp_path), _export_message())

    assert calls[-1]["status"] == "completed"
    assert encoded[0].endswith("dub_track.wav")
