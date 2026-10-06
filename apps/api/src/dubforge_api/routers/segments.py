import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.db import get_db
from dubforge_api.models import Segment as SegmentModel
from dubforge_contracts.models import Segment, SegmentReviewStatus, SegmentUpdate

router = APIRouter(prefix="/segments", tags=["segments"])


@router.patch("/{segment_id}", response_model=Segment)
async def update_segment(
    segment_id: uuid.UUID, payload: SegmentUpdate, db: AsyncSession = Depends(get_db)
) -> SegmentModel:
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

    await db.commit()
    await db.refresh(segment)
    return segment


@router.post("/{segment_id}/approve", response_model=Segment)
async def approve_segment(
    segment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> SegmentModel:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    segment.review_status = SegmentReviewStatus.APPROVED.value
    await db.commit()
    await db.refresh(segment)
    return segment


@router.post("/{segment_id}/request-changes", response_model=Segment)
async def request_segment_changes(
    segment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> SegmentModel:
    segment = await db.get(SegmentModel, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    segment.review_status = SegmentReviewStatus.NEEDS_CHANGES.value
    await db.commit()
    await db.refresh(segment)
    return segment
