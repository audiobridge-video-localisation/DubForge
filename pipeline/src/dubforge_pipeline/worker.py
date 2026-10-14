import logging
import os
import shutil
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
from dubforge_pipeline.providers.mock import MockDiarizationProvider
from dubforge_pipeline.providers.registry import (
    get_stt_provider,
    get_translation_provider,
    get_tts_provider,
)
from dubforge_pipeline.segments import combine_segments, translate_segments
from dubforge_pipeline.timing import merge_short_segments

logger = logging.getLogger(__name__)

_translator_cache: TranslationProvider | None = None
_tts_provider_cache: TTSProvider | None = None


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
    # Heavy models (e.g. NLLB) are loaded on first use by the provider
    # itself; cache the provider instance so that load happens once per
    # worker process rather than once per job.
    global _translator_cache
    if _translator_cache is None:
        _translator_cache = get_translation_provider()
    return _translator_cache


def _get_tts_provider() -> TTSProvider:
    # Same rationale as _get_translator: cache so heavy models (e.g. MMS)
    # load once per worker process rather than once per artifact.
    global _tts_provider_cache
    if _tts_provider_cache is None:
        _tts_provider_cache = get_tts_provider()
    return _tts_provider_cache


def reset_provider_cache() -> None:
    """Test hook: clear cached providers so tests can swap env/providers freely."""
    global _translator_cache, _tts_provider_cache
    _translator_cache = None
    _tts_provider_cache = None


def _get_target_lang() -> str:
    raw = os.environ.get("TARGET_LANGS", "hi")
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    if not langs:
        langs = ["hi"]
    if len(langs) > 1:
        logger.warning(
            "TARGET_LANGS=%s configures multiple languages, but each segment stores a "
            "single translated_text; only using the first language: %s",
            raw,
            langs[0],
        )
    return langs[0]


def _persist_artifact_audio(storage_root: str, artifact_id: str, source_path: str) -> str:
    """Copy provider output into persistent storage, if it actually wrote a file.

    Real providers (Edge/MMS) write to a temp location that will not survive;
    the mock provider returns a placeholder path it never writes to, so
    there's nothing to copy and the original path is reported unchanged,
    keeping the mock fallback offline and deterministic.
    """
    source = Path(source_path)
    if not source.exists():
        return source_path

    artifacts_dir = Path(storage_root) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    dest = artifacts_dir / f"{artifact_id}.wav"
    shutil.copyfile(source, dest)
    return str(dest)


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

        min_segment_ms = int(os.environ.get("MIN_SEGMENT_MS", "500"))
        merged_transcripts = merge_short_segments(transcripts, min_duration_ms=min_segment_ms)
        logger.info(
            "Job %s: merged %d transcript segments into %d (min_duration_ms=%d)",
            job_id,
            len(transcripts),
            len(merged_transcripts),
            min_segment_ms,
        )

        segments = combine_segments(merged_transcripts, speakers)
        src_lang = os.environ.get("SOURCE_LANG", "en")
        tgt_lang = _get_target_lang()
        segments = translate_segments(
            segments, _get_translator(), src_lang=src_lang, tgt_lang=tgt_lang
        )

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

    if not message.text.strip():
        logger.warning("Artifact %s has empty text; skipping synthesis", artifact_id)
        _report_artifact(
            client, api_base_url, artifact_id, ArtifactStatus.FAILED, error_message="empty text"
        )
        return

    try:
        voice_profile = _get_target_lang()
        result = _get_tts_provider().synthesize(message.text, voice_profile=voice_profile)
        audio_path = _persist_artifact_audio(storage_root, artifact_id, result.audio_path)
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
        audio_path=audio_path,
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
                process_artifact(client, api_base_url, storage_root, artifact_message)


if __name__ == "__main__":
    run()
