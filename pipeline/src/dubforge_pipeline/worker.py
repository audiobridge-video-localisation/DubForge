import logging
import os
import shutil
import tempfile
from pathlib import Path

import httpx
import redis

from dubforge_contracts.models import (
    ARTIFACT_QUEUE_KEY,
    EXPORT_QUEUE_KEY,
    JOB_QUEUE_KEY,
    ArtifactCallbackUpdate,
    ArtifactQueueMessage,
    ArtifactStatus,
    ExportJobCallbackUpdate,
    ExportJobQueueMessage,
    ExportKind,
    JobCallbackUpdate,
    JobQueueMessage,
    JobStatus,
    Segment,
    SpeakerSegment,
    TranscriptSegment,
)
from dubforge_pipeline.audio import extract_audio
from dubforge_pipeline.export_assembly import (
    build_dub_audio_track,
    encode_mp3,
    mux_mp4,
    probe_duration_ms,
)
from dubforge_pipeline.logging_config import configure_logging
from dubforge_pipeline.providers.assemblyai import transcribe_with_diarization
from dubforge_pipeline.providers.base import TranslationProvider, TTSProvider
from dubforge_pipeline.providers.mock import (
    MockDiarizationProvider,
    MockTranslationProvider,
    MockTTSProvider,
)
from dubforge_pipeline.providers.registry import get_stt_provider
from dubforge_pipeline.segments import combine_segments, translate_segments

logger = logging.getLogger(__name__)

_ARTIFACTS_SUBDIR = "artifacts"
_EXPORTS_SUBDIR = "exports"


def _report(
    client: httpx.Client,
    api_base_url: str,
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    error_message: str | None = None,
) -> None:
    payload = JobCallbackUpdate(status=status, progress=progress, error_message=error_message)
    try:
        response = client.patch(
            f"{api_base_url}/internal/jobs/{job_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for job %s", job_id)


def _get_transcription(audio_path: str) -> tuple[list[TranscriptSegment], list[SpeakerSegment]]:
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if api_key:
        return transcribe_with_diarization(audio_path, api_key)
    # AssemblyAI alone provides diarization; the registry's providers
    # (mock/whisper, selected via STT_PROVIDER) only do transcription, so
    # diarization still falls back to the mock in that case.
    return (
        get_stt_provider().transcribe(audio_path),
        MockDiarizationProvider().diarize(audio_path),
    )


def _get_translator() -> TranslationProvider:
    # No real translation provider exists yet; wire one in here following
    # the ASSEMBLYAI_API_KEY / _get_transcription pattern once one does.
    return MockTranslationProvider()


def _get_tts_provider() -> TTSProvider:
    # No real TTS provider exists yet; wire one in here following the
    # ASSEMBLYAI_API_KEY / _get_transcription pattern once one does.
    return MockTTSProvider()


def _submit_segments(
    client: httpx.Client, api_base_url: str, media_id: str, segments: list[Segment]
) -> None:
    response = client.put(
        f"{api_base_url}/internal/media/{media_id}/segments",
        json=[segment.model_dump(mode="json") for segment in segments],
    )
    response.raise_for_status()


def _report_artifact(
    client: httpx.Client,
    api_base_url: str,
    artifact_id: str,
    status: ArtifactStatus,
    audio_path: str | None = None,
    duration_ms: int | None = None,
    voice_profile: str | None = None,
    error_message: str | None = None,
) -> None:
    payload = ArtifactCallbackUpdate(
        status=status,
        audio_path=audio_path,
        duration_ms=duration_ms,
        voice_profile=voice_profile,
        error_message=error_message,
    )
    try:
        response = client.patch(
            f"{api_base_url}/internal/artifacts/{artifact_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for artifact %s", artifact_id)


def _persist_artifact_audio(audio_path: str, storage_root: str, artifact_id: str) -> str:
    """Move a TTS provider's output into the shared storage volume so the
    api process (and later, export assembly) can find it after this
    container exits. Returns a path relative to storage_root, mirroring
    Media.storage_path's convention."""
    source = Path(audio_path)
    if not source.exists():
        raise RuntimeError(f"TTS provider reported audio_path={audio_path!r} but it does not exist")
    artifacts_dir = Path(storage_root) / _ARTIFACTS_SUBDIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".wav"
    destination = artifacts_dir / f"{artifact_id}{suffix}"
    shutil.move(str(source), str(destination))
    return str(destination.relative_to(Path(storage_root)))


def process_job(
    client: httpx.Client, api_base_url: str, storage_root: str, message: JobQueueMessage
) -> None:
    job_id = str(message.job_id)
    _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=10)
    try:
        input_path = str(Path(storage_root) / message.storage_path)
        output_path = f"{input_path}.wav"
        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=30)
        extract_audio(input_path, output_path)

        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=70)
        transcripts, speakers = _get_transcription(output_path)
        segments = combine_segments(transcripts, speakers)
        # Hardcoded placeholder languages until real config/UI exists.
        segments = translate_segments(segments, _get_translator(), src_lang="en", tgt_lang="es")

        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=90)
        _submit_segments(client, api_base_url, str(message.media_id), segments)
    except Exception as exc:  # defensive: never let a bad job crash the worker loop
        logger.exception("Job %s failed", job_id)
        _report(client, api_base_url, job_id, JobStatus.FAILED, error_message=str(exc))
        return
    _report(client, api_base_url, job_id, JobStatus.COMPLETED, progress=100)


def process_artifact(
    client: httpx.Client, api_base_url: str, storage_root: str, message: ArtifactQueueMessage
) -> None:
    artifact_id = str(message.artifact_id)
    _report_artifact(client, api_base_url, artifact_id, ArtifactStatus.PROCESSING)
    try:
        # No voice-selection UI/config exists yet; hardcoded placeholder.
        voice_profile = "default"
        result = _get_tts_provider().synthesize(message.text, voice_profile=voice_profile)
        relative_audio_path = _persist_artifact_audio(result.audio_path, storage_root, artifact_id)
    except Exception as exc:  # defensive: never let a bad artifact crash the worker loop
        logger.exception("Artifact %s failed", artifact_id)
        _report_artifact(
            client, api_base_url, artifact_id, ArtifactStatus.FAILED, error_message=str(exc)
        )
        return
    _report_artifact(
        client,
        api_base_url,
        artifact_id,
        ArtifactStatus.COMPLETED,
        audio_path=relative_audio_path,
        duration_ms=result.actual_duration_ms,
        voice_profile=voice_profile,
    )


def _report_export(
    client: httpx.Client,
    api_base_url: str,
    export_job_id: str,
    status: JobStatus,
    progress: int | None = None,
    output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    payload = ExportJobCallbackUpdate(
        status=status, progress=progress, output_path=output_path, error_message=error_message
    )
    try:
        response = client.patch(
            f"{api_base_url}/internal/export-jobs/{export_job_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for export job %s", export_job_id)


def _fetch_segments(client: httpx.Client, api_base_url: str, media_id: str) -> list[Segment]:
    response = client.get(f"{api_base_url}/internal/media/{media_id}/segments")
    response.raise_for_status()
    return [Segment.model_validate(item) for item in response.json()]


def process_export_job(
    client: httpx.Client, api_base_url: str, storage_root: str, message: ExportJobQueueMessage
) -> None:
    export_job_id = str(message.export_job_id)
    _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=10)
    try:
        segments = _fetch_segments(client, api_base_url, str(message.media_id))
        video_path = str(Path(storage_root) / message.media_storage_path)
        total_duration_ms = probe_duration_ms(video_path)

        segment_audio: list[tuple[int, str]] = []
        for segment in segments:
            if segment.artifact is None or segment.artifact.audio_path is None:
                raise RuntimeError(f"segment {segment.id} has no usable audio artifact")
            abs_path = str(Path(storage_root) / segment.artifact.audio_path)
            if not Path(abs_path).exists():
                raise RuntimeError(
                    f"audio file missing on disk for segment {segment.id}: {abs_path}"
                )
            segment_audio.append((segment.start_ms, abs_path))

        _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=30)

        with tempfile.TemporaryDirectory() as tmp_dir:
            dub_wav = str(Path(tmp_dir) / "dub_track.wav")
            build_dub_audio_track(segment_audio, total_duration_ms, dub_wav)
            _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=60)

            exports_dir = Path(storage_root) / _EXPORTS_SUBDIR
            exports_dir.mkdir(parents=True, exist_ok=True)
            if message.kind == ExportKind.MP3:
                output_path = exports_dir / f"{export_job_id}.mp3"
                encode_mp3(dub_wav, str(output_path))
            else:
                output_path = exports_dir / f"{export_job_id}.mp4"
                mux_mp4(video_path, dub_wav, str(output_path))
            _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=90)
    except Exception as exc:  # defensive: never let a bad export job crash the worker loop
        logger.exception("Export job %s failed", export_job_id)
        _report_export(
            client, api_base_url, export_job_id, JobStatus.FAILED, error_message=str(exc)
        )
        return

    relative_output = str(output_path.relative_to(Path(storage_root)))
    _report_export(
        client,
        api_base_url,
        export_job_id,
        JobStatus.COMPLETED,
        progress=100,
        output_path=relative_output,
    )


def run() -> None:
    configure_logging()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    storage_root = os.environ.get("STORAGE_DIR", "/app/data")

    # socket_timeout must exceed BLPOP's block timeout below, or redis-py's
    # client-side read timeout races the server-side block and raises
    # spurious TimeoutErrors on every idle poll.
    r = redis.from_url(redis_url, decode_responses=True, socket_timeout=10)
    logger.info(
        "DubForge worker started; listening on %s, %s, %s",
        JOB_QUEUE_KEY,
        ARTIFACT_QUEUE_KEY,
        EXPORT_QUEUE_KEY,
    )

    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                item = r.blpop([JOB_QUEUE_KEY, ARTIFACT_QUEUE_KEY, EXPORT_QUEUE_KEY], timeout=5)
            except redis.RedisError:
                logger.exception("Redis connection error; retrying")
                continue
            if item is None:
                continue
            key, raw = item
            if key == JOB_QUEUE_KEY:
                try:
                    job_message = JobQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed job message: %s", raw)
                    continue
                process_job(client, api_base_url, storage_root, job_message)
            elif key == ARTIFACT_QUEUE_KEY:
                try:
                    artifact_message = ArtifactQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed artifact message: %s", raw)
                    continue
                process_artifact(client, api_base_url, storage_root, artifact_message)
            else:
                try:
                    export_message = ExportJobQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed export job message: %s", raw)
                    continue
                process_export_job(client, api_base_url, storage_root, export_message)


if __name__ == "__main__":
    run()
