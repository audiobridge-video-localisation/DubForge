import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class SegmentReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_CHANGES = "needs_changes"


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    storage_path: str
    created_at: datetime
    ready_for_dubbing: bool = False


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


class Segment(BaseModel):
    """An ordered, speaker-labeled transcript segment for a piece of media.

    `id` defaults to a fresh UUID so the worker can build these before
    they're persisted (e.g. for the bulk-replace queue payload); the api
    assigns the real row id on insert and ignores whatever id was sent.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    index: int
    start_ms: int
    end_ms: int
    duration_ms: int
    speaker_label: str
    text: str
    translated_text: str | None = None
    review_status: SegmentReviewStatus = SegmentReviewStatus.PENDING


class SegmentUpdate(BaseModel):
    """Partial update for a single segment; only provided fields change."""

    text: str | None = None
    translated_text: str | None = None
    speaker_label: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "SegmentUpdate":
        if self.start_ms is not None and self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValueError("end_ms must be >= 0")
        if self.start_ms is not None and self.end_ms is not None and self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be less than end_ms")
        return self


JOB_QUEUE_KEY = "dubforge:jobs"
