import logging
import os
from pathlib import Path

import httpx
import redis

from dubforge_contracts.models import (
    JOB_QUEUE_KEY,
    JobCallbackUpdate,
    JobQueueMessage,
    JobStatus,
)
from dubforge_pipeline.audio import extract_audio
from dubforge_pipeline.logging_config import configure_logging

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


def process_job(
    client: httpx.Client, api_base_url: str, storage_root: str, message: JobQueueMessage
) -> None:
    job_id = str(message.job_id)
    _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=10)
    try:
        input_path = str(Path(storage_root) / message.storage_path)
        output_path = f"{input_path}.wav"
        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=40)
        extract_audio(input_path, output_path)
        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=80)
    except Exception as exc:  # defensive: never let a bad job crash the worker loop
        logger.exception("Job %s failed", job_id)
        _report(client, api_base_url, job_id, JobStatus.FAILED, error_message=str(exc))
        return
    _report(client, api_base_url, job_id, JobStatus.COMPLETED, progress=100)


def run() -> None:
    configure_logging()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    storage_root = os.environ.get("STORAGE_DIR", "/app/data")

    # socket_timeout must exceed BLPOP's block timeout below, or redis-py's
    # client-side read timeout races the server-side block and raises
    # spurious TimeoutErrors on every idle poll.
    r = redis.from_url(redis_url, decode_responses=True, socket_timeout=10)
    logger.info("DubForge worker started; listening on %s", JOB_QUEUE_KEY)

    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                item = r.blpop([JOB_QUEUE_KEY], timeout=5)
            except redis.RedisError:
                logger.exception("Redis connection error; retrying")
                continue
            if item is None:
                continue
            _, raw = item
            try:
                message = JobQueueMessage.model_validate_json(raw)
            except Exception:
                logger.exception("Dropping malformed queue message: %s", raw)
                continue
            process_job(client, api_base_url, storage_root, message)


if __name__ == "__main__":
    run()
