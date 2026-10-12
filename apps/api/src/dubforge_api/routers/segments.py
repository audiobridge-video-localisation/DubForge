import uuid

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.db import get_db
from dubforge_api.models import Artifact as ArtifactModel
from dubforge_api.models import Segment as SegmentModel
from dubforge_api.redis_client import get_redis
from dubforge_api.schemas import segment_to_contract
from dubforge_contracts.models import (
    ARTIFACT_QUEUE_KEY,
    Artifact,
    ArtifactQueueMessage,
    ArtifactStatus,
    Segment,
    SegmentReviewStatus,
    SegmentUpdate,
)

router = APIRouter(prefix="/segments", tags=["segments"])


async def _get_artifact_for_segment(
    segment_id: uuid.UUID, db: AsyncSession
) -> ArtifactModel | None:
    # Queried directly by FK rather than via the Segment.artifact
    # relationship: that one-to-one selectinload intermittently left
    # `updated_at` in a state that raised a SQLAlchemy async/greenlet error
    # on serialization, even when apparently eager-loaded.
    result = await db.execute(select(ArtifactModel).where(ArtifactModel.segment_id == segment_id))
    return result.scalar_one_or_none()


@router.patch("/{segment_id}", response_model=Segment)
async def update_segment(
    segment_id: uuid.UUID, payload: SegmentUpdate, db: AsyncSession = Depends(get_db)
) -> Segment:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    new_start = payload.start_ms if payload.start_ms is not None else segment.start_ms
    new_end = payload.end_ms if payload.end_ms is not None else segment.end_ms
    if new_start < 0 or new_start >= new_end:
        raise HTTPException(status_code=422, detail="start_ms must be >= 0 and less than end_ms")

    changed = False
    if payload.text is not None:
        segment.text = payload.text
        changed = True
    if payload.translated_text is not None:
        segment.translated_text = payload.translated_text
        changed = True
    if payload.speaker_label is not None:
        segment.speaker_label = payload.speaker_label
        changed = True
    if payload.start_ms is not None or payload.end_ms is not None:
        segment.start_ms = new_start
        segment.end_ms = new_end
        segment.duration_ms = new_end - new_start
        changed = True

    if changed and segment.review_status != SegmentReviewStatus.PENDING.value:
        segment.review_status = SegmentReviewStatus.PENDING.value

    artifact = await _get_artifact_for_segment(segment_id, db)
    if changed and artifact is not None and artifact.status != ArtifactStatus.OUTDATED.value:
        artifact.status = ArtifactStatus.OUTDATED.value
        await db.commit()
        # updated_at has onupdate=func.now(); expire_on_commit=False keeps
        # the rest of the object populated but this server-computed column
        # still needs an explicit refresh before it's safe to read again.
        await db.refresh(artifact, attribute_names=["updated_at"])
    else:
        await db.commit()
    return segment_to_contract(segment, artifact)


@router.post("/{segment_id}/approve", response_model=Segment)
async def approve_segment(segment_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Segment:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    segment.review_status = SegmentReviewStatus.APPROVED.value
    artifact = await _get_artifact_for_segment(segment_id, db)
    await db.commit()
    return segment_to_contract(segment, artifact)


@router.post("/{segment_id}/request-changes", response_model=Segment)
async def request_segment_changes(
    segment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Segment:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    segment.review_status = SegmentReviewStatus.NEEDS_CHANGES.value
    artifact = await _get_artifact_for_segment(segment_id, db)
    await db.commit()
    return segment_to_contract(segment, artifact)


@router.post("/{segment_id}/regenerate", response_model=Artifact)
async def regenerate_segment(
    segment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ArtifactModel:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    artifact = await _get_artifact_for_segment(segment_id, db)
    if artifact is None:
        artifact = ArtifactModel(segment_id=segment.id, status=ArtifactStatus.PENDING.value)
        db.add(artifact)
    else:
        artifact.status = ArtifactStatus.PENDING.value
        artifact.audio_path = None
        artifact.error_message = None
        artifact.retry_count += 1
    await db.commit()
    await db.refresh(artifact)

    message = ArtifactQueueMessage(
        artifact_id=artifact.id,
        segment_id=segment.id,
        text=segment.translated_text or segment.text,
    )
    await redis.rpush(ARTIFACT_QUEUE_KEY, message.model_dump_json())

    return artifact
