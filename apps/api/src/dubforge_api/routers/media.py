import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import Settings, get_settings
from dubforge_api.db import get_db
from dubforge_api.models import Job, Media, Project
from dubforge_api.readiness import require_dub_ready
from dubforge_api.redis_client import get_redis
from dubforge_api.schemas import MediaWithJob
from dubforge_api.storage import resolve_stored_file
from dubforge_contracts.models import (
    DEFAULT_TARGET_LANG,
    JOB_QUEUE_KEY,
    SUPPORTED_TARGET_LANGS,
    JobQueueMessage,
    JobRead,
    JobStatus,
    MediaRead,
)

router = APIRouter(prefix="/projects", tags=["media"])
media_router = APIRouter(prefix="/media", tags=["media"])


@router.post("/{project_id}/media", response_model=MediaWithJob, status_code=201)
async def upload_media(
    project_id: uuid.UUID,
    file: UploadFile,
    # Chosen once, at upload time: translation (and the first dub pass) runs immediately
    # off this job, so unlike voice_gender there's no later step where picking a language
    # would still be in time for it. Defaulted so existing clients that don't send it keep
    # getting today's behavior.
    target_lang: str = Form(DEFAULT_TARGET_LANG),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MediaWithJob:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if target_lang not in SUPPORTED_TARGET_LANGS:
        valid_options = ", ".join(SUPPORTED_TARGET_LANGS)
        raise HTTPException(
            status_code=422, detail=f"target_lang must be one of: {valid_options}"
        )

    safe_name = Path(file.filename or "upload").name
    relative_path = f"{project_id}/{uuid.uuid4()}_{safe_name}"
    destination = Path(settings.storage_dir) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(await file.read())

    media = Media(
        project_id=project_id,
        filename=safe_name,
        storage_path=relative_path,
        target_lang=target_lang,
    )
    job = Job(media=media, status=JobStatus.PENDING.value, progress=0)
    db.add(media)
    db.add(job)
    await db.commit()
    await db.refresh(media, attribute_names=["created_at"])
    await db.refresh(job, attribute_names=["created_at", "updated_at"])

    message = JobQueueMessage(
        job_id=job.id, media_id=media.id, storage_path=relative_path, target_lang=target_lang
    )
    try:
        await redis.rpush(JOB_QUEUE_KEY, message.model_dump_json())
    except Exception as exc:
        job.status = JobStatus.FAILED.value
        job.error_message = f"failed to enqueue job: {exc}"
        await db.commit()
        await db.refresh(job, attribute_names=["updated_at"])

    return MediaWithJob(media=MediaRead.model_validate(media), job=JobRead.model_validate(job))


@media_router.post("/{media_id}/ready-for-dubbing", response_model=MediaRead)
async def mark_ready_for_dubbing(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Media:
    media = await db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    await require_dub_ready(media_id, db, "marking ready for dubbing")

    media.ready_for_dubbing = True
    await db.commit()
    await db.refresh(media)
    return media


_SOURCE_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}


@media_router.get("/{media_id}/source")
async def get_source_media(
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """The uploaded file, for playback in the review screen (supports range requests)."""
    media = await db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    path = resolve_stored_file(settings.storage_dir, media.storage_path)
    media_type = _SOURCE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)
