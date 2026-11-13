import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Target languages the pipeline can actually translate/dub into today. Kept here (rather
# than in the api or pipeline package) since both sides need to agree on what's valid: the
# api validates an upload's target_lang against this before queuing a job, and the pipeline's
# own per-language maps (NLLB lang codes, TTS voice pools) are expected to cover the same set.
SUPPORTED_TARGET_LANGS: tuple[str, ...] = ("hi", "bn")
DEFAULT_TARGET_LANG = "hi"


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
    # How much faster than its normal pace (TTS_RATE, if set) the voice was asked to speak
    # to fit the line (1.0 = normal). None means this is not a real voice (the mock), so
    # nothing can be learned from it.
    speech_rate: float | None = None


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SegmentReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_CHANGES = "needs_changes"


class TranslationSource(StrEnum):
    """Where a segment's translated text came from, so a person's edits are never overwritten."""

    MACHINE = "machine"
    EDITED = "edited"  # a person changed it
    AUTO_SHORTENED = "auto_shortened"  # the worker swapped in a shorter wording to fit the time


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
    # Longer than its room, but the export absorbs it by also slowing the video behind
    # the line (see dubforge_pipeline.export_assembly.plan_timeline). Usable.
    STRETCHED = "stretched"
    READY = "ready"


# Statuses whose audio can go into an export.
USABLE_AUDIO_STATUSES = frozenset({SegmentAudioStatus.READY, SegmentAudioStatus.STRETCHED})


# The most a dubbed line is ever sped up past the voice's normal pace, counting every step:
# the voice speaking faster when it is synthesised and the speed-up at export together.
# Past this it sounds rushed, so a line that would need more is flagged for a person.
MAX_SPEEDUP = 1.25
# Audio shorter than this share of its slot is more likely a clipped or silent take than
# a terse translation.
MIN_AUDIO_SHARE = 0.25
# The most the export slows the video behind a long line (setpts). Like a 1.25x speed-up,
# 1.25x slower talking footage is hard to notice.
MAX_VIDEO_SLOWDOWN = 1.25
# Audio up to this many times its room fits with both: 1.25x faster speech over 1.25x
# slower video. Longer than that is a mismatch a person has to look at.
MAX_TIMELINE_STRETCH = MAX_SPEEDUP * MAX_VIDEO_SLOWDOWN


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    storage_path: str
    created_at: datetime
    ready_for_dubbing: bool = False
    target_lang: str = DEFAULT_TARGET_LANG


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
    # The language chosen for this media at upload time. Defaulted rather than optional:
    # every job needs a translation target, and this keeps older messages (from before this
    # field existed) loadable without a migration of in-flight queue data.
    target_lang: str = DEFAULT_TARGET_LANG


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
    # How much the voice was already sped up for this take (see MAX_SPEEDUP).
    speedup: float = 1.0
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime


def segment_room_ms(start_ms: int, duration_ms: int, next_start_ms: int | None) -> int:
    """How long a dub may run: from this line's start to the next line's start.

    The spoken line itself is only part of it; the silence before the next line is free
    room, and the export step places audio the same way. The last line has no next line,
    so its room is just its own length.
    """
    if next_start_ms is None:
        return duration_ms
    return max(duration_ms, next_start_ms - start_ms)


def remaining_speedup(already: float) -> float:
    """How much more a take that was already sped up `already` times may be sped up."""
    return max(MAX_SPEEDUP / max(already, 1.0), 1.0)


def compute_audio_status(
    segment_duration_ms: int, artifact: Artifact | None, room_ms: int | None = None
) -> SegmentAudioStatus:
    """Derive a single usable-audio status from a segment's expected
    duration (and the room it may spill into) and its (possibly absent) dubbed-audio
    artifact."""

    if artifact is None:
        return SegmentAudioStatus.NO_AUDIO
    if artifact.status in (ArtifactStatus.PENDING, ArtifactStatus.PROCESSING):
        return SegmentAudioStatus.PENDING
    if artifact.status == ArtifactStatus.FAILED:
        return SegmentAudioStatus.FAILED
    if artifact.status == ArtifactStatus.OUTDATED:
        return SegmentAudioStatus.OUTDATED

    # COMPLETED: only audio LONGER than export can speed up into its room is a problem;
    # shorter audio just leaves silence, which is fine, unless so short it is likely
    # broken. Longer audio the export can absorb by also slowing the video is
    # "stretched"; past that it is a mismatch.
    if artifact.duration_ms is None:
        return SegmentAudioStatus.MISMATCH
    if artifact.duration_ms <= 0:
        return SegmentAudioStatus.FAILED
    if artifact.duration_ms < MIN_AUDIO_SHARE * segment_duration_ms:
        return SegmentAudioStatus.MISMATCH
    available_ms = max(room_ms or 0, segment_duration_ms)
    fits_ms = available_ms * remaining_speedup(artifact.speedup)
    if artifact.duration_ms <= fits_ms:
        return SegmentAudioStatus.READY
    if artifact.duration_ms <= fits_ms * MAX_VIDEO_SLOWDOWN:
        return SegmentAudioStatus.STRETCHED
    return SegmentAudioStatus.MISMATCH


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
    # how long a dub may run: up to the next line's start (see segment_room_ms)
    room_ms: int | None = None
    speaker_label: str
    text: str
    translated_text: str | None = None
    translation_source: TranslationSource = TranslationSource.MACHINE
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
    # The segment's slot length. The worker time-fits the generated audio to it when it is
    # close enough to stretch without sounding rushed. None = leave the audio as generated.
    target_duration_ms: int | None = None
    # The line in the source language, and whether the worker may swap in a shorter wording
    # when the dub still does not fit. False once a person has edited the translation.
    source_text: str | None = None
    may_rewrite: bool = False
    # The media's target language, copied in at regenerate time so the voice matches what
    # the line was actually translated into.
    target_lang: str = DEFAULT_TARGET_LANG


class ArtifactCallbackUpdate(BaseModel):
    """Partial update the worker reports back to the api."""

    status: ArtifactStatus
    audio_path: str | None = None
    duration_ms: int | None = None
    voice_profile: str | None = None
    speedup: float | None = None
    error_message: str | None = None
    # Set when the worker shortened the wording to make the audio fit; the audio matches it.
    translated_text: str | None = None


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
    target_lang: str = DEFAULT_TARGET_LANG


class ExportJobCallbackUpdate(BaseModel):
    """Partial update the worker reports back to the api."""

    status: JobStatus
    progress: int | None = None
    output_path: str | None = None
    error_message: str | None = None


JOB_QUEUE_KEY = "dubforge:jobs"
ARTIFACT_QUEUE_KEY = "dubforge:artifacts"
EXPORT_QUEUE_KEY = "dubforge:exports"
