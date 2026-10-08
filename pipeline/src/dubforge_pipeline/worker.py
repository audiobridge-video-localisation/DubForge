import logging
import os
from pathlib import Path

import httpx
import redis

from dubforge_contracts.models import (
    ARTIFACT_QUEUE_KEY,
    JOB_QUEUE_KEY,
    ArtifactCallbackUpdate,
    ArtifactQueueMessage,
    ArtifactStatus,
    JobCallbackUpdate,
    JobQueueMessage,
    JobStatus,
    Segment,
    SpeakerSegment,
    TranscriptSegment,
)
from dubforge_pipeline.audio import extract_audio
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
    error_message: str | None = None,
) -> None:
    payload = ArtifactCallbackUpdate(
        status=status,
        audio_path=audio_path,
        duration_ms=duration_ms,
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
    client: httpx.Client, api_base_url: str, message: ArtifactQueueMessage
) -> None:
    artifact_id = str(message.artifact_id)
    _report_artifact(client, api_base_url, artifact_id, ArtifactStatus.PROCESSING)
    try:
        # No voice-selection UI/config exists yet; hardcoded placeholder.
        result = _get_tts_provider().synthesize(message.text, voice_profile="default")
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
        audio_path=result.audio_path,
        duration_ms=result.actual_duration_ms,
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
    logger.info("DubForge worker started; listening on %s, %s", JOB_QUEUE_KEY, ARTIFACT_QUEUE_KEY)

    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                item = r.blpop([JOB_QUEUE_KEY, ARTIFACT_QUEUE_KEY], timeout=5)
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
            else:
                try:
                    artifact_message = ArtifactQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed artifact message: %s", raw)
                    continue
                process_artifact(client, api_base_url, artifact_message)


if __name__ == "__main__":
    run()
