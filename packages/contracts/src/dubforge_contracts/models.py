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


class ArtifactStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    OUTDATED = "outdated"


class SegmentAudioStatus(StrEnum):
    """Derived, user-facing answer to "is this segment's audio usable?"."""

    NO_AUDIO = "no_audio"
    PENDING = "pending"
    FAILED = "failed"
    OUTDATED = "outdated"
    MISMATCH = "mismatch"
    READY = "ready"


AUDIO_MISMATCH_ABS_TOLERANCE_MS = 300
# 0.25 matches MAX_ATEMPO (1.25) in dubforge_pipeline.export_assembly: audio up to
# 25% longer than its slot can be sped up to fit at export time.
AUDIO_MISMATCH_REL_TOLERANCE = 0.25


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


class Artifact(BaseModel):
    """A dubbed-audio artifact generated for a single segment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: ArtifactStatus = ArtifactStatus.PENDING
    audio_path: str | None = None
    duration_ms: int | None = None
    voice_profile: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime


def compute_audio_status(segment_duration_ms: int, artifact: Artifact | None) -> SegmentAudioStatus:
    """Derive a single usable-audio status from a segment's expected
    duration and its (possibly absent) dubbed-audio artifact."""

    if artifact is None:
        return SegmentAudioStatus.NO_AUDIO
    if artifact.status in (ArtifactStatus.PENDING, ArtifactStatus.PROCESSING):
        return SegmentAudioStatus.PENDING
    if artifact.status == ArtifactStatus.FAILED:
        return SegmentAudioStatus.FAILED
    if artifact.status == ArtifactStatus.OUTDATED:
        return SegmentAudioStatus.OUTDATED

    # COMPLETED: only audio LONGER than its slot beyond tolerance is a mismatch;
    # shorter audio just leaves silence, which is fine.
    if artifact.duration_ms is None:
        return SegmentAudioStatus.MISMATCH
    tolerance_ms = max(
        AUDIO_MISMATCH_ABS_TOLERANCE_MS, AUDIO_MISMATCH_REL_TOLERANCE * segment_duration_ms
    )
    if artifact.duration_ms - segment_duration_ms > tolerance_ms:
        return SegmentAudioStatus.MISMATCH
    return SegmentAudioStatus.READY


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
    artifact: Artifact | None = None
    audio_status: SegmentAudioStatus = SegmentAudioStatus.NO_AUDIO


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


class ArtifactQueueMessage(BaseModel):
    """Message pushed by the api and consumed by the pipeline worker."""

    artifact_id: uuid.UUID
    segment_id: uuid.UUID
    text: str


class ArtifactCallbackUpdate(BaseModel):
    """Partial update the worker reports back to the api."""

    status: ArtifactStatus
    audio_path: str | None = None
    duration_ms: int | None = None
    voice_profile: str | None = None
    error_message: str | None = None


class ExportKind(StrEnum):
    MP3 = "mp3"
    MP4 = "mp4"


class ExportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    media_id: uuid.UUID
    kind: ExportKind
    status: JobStatus
    progress: int
    output_path: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class ExportJobQueueMessage(BaseModel):
    """Message pushed by the api and consumed by the pipeline worker."""

    export_job_id: uuid.UUID
    media_id: uuid.UUID
    kind: ExportKind
    media_storage_path: str


class ExportJobCallbackUpdate(BaseModel):
    """Partial update the worker reports back to the api."""

    status: JobStatus
    progress: int | None = None
    output_path: str | None = None
    error_message: str | None = None


JOB_QUEUE_KEY = "dubforge:jobs"
ARTIFACT_QUEUE_KEY = "dubforge:artifacts"
EXPORT_QUEUE_KEY = "dubforge:exports"
