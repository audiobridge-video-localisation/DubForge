"""Endpoints called by the pipeline worker, not by the frontend.

No auth is applied here, consistent with every other endpoint in this app
today — this is an internal trust-boundary callback target for the worker.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.db import get_db
from dubforge_api.models import Job, Media
from dubforge_api.models import Segment as SegmentModel
from dubforge_contracts.models import JobCallbackUpdate, JobRead, Segment

router = APIRouter(prefix="/internal", tags=["internal"])


@router.patch("/jobs/{job_id}", response_model=JobRead)
async def update_job(
    job_id: uuid.UUID, payload: JobCallbackUpdate, db: AsyncSession = Depends(get_db)
) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = payload.status.value
    if payload.progress is not None:
        job.progress = payload.progress
    if payload.error_message is not None:
        job.error_message = payload.error_message[:2000]
    await db.commit()
    await db.refresh(job, attribute_names=["updated_at"])
    return job


@router.put("/media/{media_id}/segments", status_code=status.HTTP_204_NO_CONTENT)
async def replace_segments(
    media_id: uuid.UUID, payload: list[Segment], db: AsyncSession = Depends(get_db)
) -> Response:
    media = await db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    await db.execute(delete(SegmentModel).where(SegmentModel.media_id == media_id))
    db.add_all(
        SegmentModel(
            media_id=media_id,
            index=segment.index,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            duration_ms=segment.duration_ms,
            speaker_label=segment.speaker_label,
            text=segment.text,
        )
        for segment in payload
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
