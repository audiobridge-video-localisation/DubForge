"""Endpoints called by the pipeline worker, not by the frontend.

No auth is applied here, consistent with every other endpoint in this app
today — this is an internal trust-boundary callback target for the worker.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.db import get_db
from dubforge_api.models import Job
from dubforge_contracts.models import JobCallbackUpdate, JobRead

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
