import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from dubforge_api.models import Artifact as ArtifactModel
from dubforge_api.models import Segment as SegmentModel
from dubforge_contracts.models import (
    Artifact,
    JobRead,
    MediaRead,
    Segment,
    SegmentReviewStatus,
    TranslationSource,
    compute_audio_status,
    segment_room_ms,
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class MediaWithJob(BaseModel):
    media: MediaRead
    job: JobRead
    segments: list[Segment] = []
    approved_count: int = 0
    total_count: int = 0
    usable_audio_count: int = 0


class ProjectDetailRead(ProjectRead):
    media: list[MediaWithJob] = []


def rooms_by_segment(segments: list[SegmentModel]) -> dict[uuid.UUID, int]:
    """Each segment's room (see segment_room_ms) given all the segments of one media."""
    ordered = sorted(segments, key=lambda s: (s.start_ms, s.index))
    rooms: dict[uuid.UUID, int] = {}
    for position, s in enumerate(ordered):
        following = ordered[position + 1].start_ms if position + 1 < len(ordered) else None
        rooms[s.id] = segment_room_ms(s.start_ms, s.duration_ms, following)
    return rooms


def segment_to_contract(
    segment: SegmentModel, artifact: ArtifactModel | None, room_ms: int | None = None
) -> Segment:
    # Built explicitly field-by-field rather than via Segment.model_validate
    # on the ORM object: accessing an eager-loaded one-to-one relationship's
    # columns this way intermittently raised a SQLAlchemy async/greenlet
    # error during Pydantic validation. Querying the artifact directly by
    # its segment_id FK, then passing it in here, avoids the relationship
    # entirely.
    artifact_contract = Artifact.model_validate(artifact) if artifact else None
    return Segment(
        id=segment.id,
        index=segment.index,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        duration_ms=segment.duration_ms,
        room_ms=room_ms,
        speaker_label=segment.speaker_label,
        text=segment.text,
        translated_text=segment.translated_text,
        translation_source=TranslationSource(segment.translation_source),
        review_status=SegmentReviewStatus(segment.review_status),
        artifact=artifact_contract,
        audio_status=compute_audio_status(segment.duration_ms, artifact_contract, room_ms),
    )
