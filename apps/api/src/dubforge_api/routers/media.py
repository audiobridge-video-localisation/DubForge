import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import Settings, get_settings
from dubforge_api.db import get_db
from dubforge_api.models import Job, Media, Project
from dubforge_api.redis_client import get_redis
from dubforge_api.schemas import MediaWithJob
from dubforge_contracts.models import JOB_QUEUE_KEY, JobQueueMessage, JobRead, JobStatus, MediaRead

router = APIRouter(prefix="/projects", tags=["media"])


@router.post("/{project_id}/media", response_model=MediaWithJob, status_code=201)
async def upload_media(
    project_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MediaWithJob:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    safe_name = Path(file.filename or "upload").name
    relative_path = f"{project_id}/{uuid.uuid4()}_{safe_name}"
    destination = Path(settings.storage_dir) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(await file.read())

    media = Media(project_id=project_id, filename=safe_name, storage_path=relative_path)
    job = Job(media=media, status=JobStatus.PENDING.value, progress=0)
    db.add(media)
    db.add(job)
    await db.commit()
    await db.refresh(media, attribute_names=["created_at"])
    await db.refresh(job, attribute_names=["created_at", "updated_at"])

    message = JobQueueMessage(job_id=job.id, media_id=media.id, storage_path=relative_path)
    try:
        await redis.rpush(JOB_QUEUE_KEY, message.model_dump_json())
    except Exception as exc:
        job.status = JobStatus.FAILED.value
        job.error_message = f"failed to enqueue job: {exc}"
        await db.commit()
        await db.refresh(job, attribute_names=["updated_at"])

    return MediaWithJob(media=MediaRead.model_validate(media), job=JobRead.model_validate(job))
