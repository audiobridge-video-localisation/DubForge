import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.models import Artifact as ArtifactModel
from dubforge_api.models import Segment as SegmentModel
from dubforge_api.schemas import rooms_by_segment
from dubforge_contracts.models import (
    Artifact,
    SegmentAudioStatus,
    SegmentReviewStatus,
    compute_audio_status,
)


async def require_dub_ready(media_id: uuid.UUID, db: AsyncSession, action: str) -> None:
    """409 unless every segment is approved and has usable dubbed audio.

    `action` completes the message: "All segments must be ... before {action}".
    """
    detail = f"All segments must be approved and have usable dubbed audio before {action}"

    result = await db.execute(
        select(SegmentModel).where(SegmentModel.media_id == media_id).order_by(SegmentModel.index)
    )
    segments = list(result.scalars().all())
    if not segments:
        raise HTTPException(status_code=409, detail=detail)

    artifacts_result = await db.execute(
        select(ArtifactModel).where(ArtifactModel.segment_id.in_([s.id for s in segments]))
    )
    artifact_by_segment_id = {a.segment_id: a for a in artifacts_result.scalars()}

    rooms = rooms_by_segment(segments)
    approved = sum(1 for s in segments if s.review_status == SegmentReviewStatus.APPROVED.value)
    usable = 0
    for s in segments:
        artifact_row = artifact_by_segment_id.get(s.id)
        artifact_contract = Artifact.model_validate(artifact_row) if artifact_row else None
        status = compute_audio_status(s.duration_ms, artifact_contract, rooms.get(s.id))
        if status == SegmentAudioStatus.READY:
            usable += 1

    if approved != len(segments) or usable != len(segments):
        raise HTTPException(status_code=409, detail=detail)
