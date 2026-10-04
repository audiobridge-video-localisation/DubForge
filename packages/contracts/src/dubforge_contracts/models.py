import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TranscriptSegment(BaseModel):
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


class SpeakerSegment(BaseModel):
    start_ms: int
    end_ms: int
    speaker_label: str


class AudioResult(BaseModel):
    audio_path: str
    actual_duration_ms: int


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    storage_path: str
    created_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    media_id: uuid.UUID
    status: JobStatus
    progress: int
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class JobQueueMessage(BaseModel):
    """Message pushed by the api and consumed by the pipeline worker."""

    job_id: uuid.UUID
    media_id: uuid.UUID
    storage_path: str


class JobCallbackUpdate(BaseModel):
    """Partial update the worker reports back to the api."""

    status: JobStatus
    progress: int | None = None
    error_message: str | None = None


JOB_QUEUE_KEY = "dubforge:jobs"
