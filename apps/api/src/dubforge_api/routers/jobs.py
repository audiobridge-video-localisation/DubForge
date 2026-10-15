import uuid

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dubforge_api.db import get_db
from dubforge_api.models import Job
from dubforge_api.redis_client import get_redis
from dubforge_contracts.models import JOB_QUEUE_KEY, JobQueueMessage, JobRead, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Job:
    result = await db.execute(select(Job).options(selectinload(Job.media)).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    job.status = JobStatus.PENDING.value
    job.progress = 0
    job.error_message = None
    job.retry_count += 1
    await db.commit()
    await db.refresh(job, attribute_names=["updated_at"])

    message = JobQueueMessage(
        job_id=job.id, media_id=job.media_id, storage_path=job.media.storage_path
    )
    await redis.rpush(JOB_QUEUE_KEY, message.model_dump_json())

    return job
