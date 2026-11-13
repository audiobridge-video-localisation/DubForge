import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import Settings, get_settings
from dubforge_api.db import get_db
from dubforge_api.models import ExportJob, Media
from dubforge_api.models import Segment as SegmentModel
from dubforge_api.readiness import require_dub_ready
from dubforge_api.redis_client import get_redis
from dubforge_api.storage import resolve_stored_file
from dubforge_contracts.export import segments_to_srt, segments_to_vtt
from dubforge_contracts.models import (
    EXPORT_QUEUE_KEY,
    ExportJobQueueMessage,
    ExportJobRead,
    ExportKind,
    JobStatus,
    TranscriptSegment,
)

media_export_router = APIRouter(prefix="/media", tags=["exports"])
export_jobs_router = APIRouter(prefix="/export-jobs", tags=["exports"])


async def _load_media_or_404(media_id: uuid.UUID, db: AsyncSession) -> Media:
    media = await db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return media


async def _ordered_segments(media_id: uuid.UUID, db: AsyncSession) -> list[SegmentModel]:
    result = await db.execute(
        select(SegmentModel).where(SegmentModel.media_id == media_id).order_by(SegmentModel.index)
    )
    return list(result.scalars().all())


@media_export_router.get("/{media_id}/export/srt")
async def export_srt(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    await _load_media_or_404(media_id, db)
    segments = await _ordered_segments(media_id, db)
    if not segments:
        raise HTTPException(status_code=409, detail="No segments to export")

    transcript_segments = [
        TranscriptSegment(start_ms=s.start_ms, end_ms=s.end_ms, text=s.translated_text or s.text)
        for s in segments
    ]
    body = segments_to_srt(transcript_segments)
    return PlainTextResponse(
        body,
        media_type="application/x-subrip",
        headers={"Content-Disposition": 'attachment; filename="dub.srt"'},
    )


@media_export_router.get("/{media_id}/export/vtt")
async def export_vtt(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    await _load_media_or_404(media_id, db)
    segments = await _ordered_segments(media_id, db)
    if not segments:
        raise HTTPException(status_code=409, detail="No segments to export")

    transcript_segments = [
        TranscriptSegment(start_ms=s.start_ms, end_ms=s.end_ms, text=s.translated_text or s.text)
        for s in segments
    ]
    body = segments_to_vtt(transcript_segments)
    return PlainTextResponse(
        body,
        media_type="text/vtt",
        headers={"Content-Disposition": 'attachment; filename="dub.vtt"'},
    )


async def _create_export_job(
    media_id: uuid.UUID,
    kind: ExportKind,
    db: AsyncSession,
    redis: Redis,
    accept_long_lines: bool = False,
) -> ExportJob:
    media = await _load_media_or_404(media_id, db)
    await require_dub_ready(media_id, db, "exporting", accept_long_lines=accept_long_lines)

    export_job = ExportJob(
        media_id=media_id, kind=kind.value, status=JobStatus.PENDING.value, progress=0
    )
    db.add(export_job)
    await db.commit()
    await db.refresh(export_job, attribute_names=["created_at", "updated_at"])

    message = ExportJobQueueMessage(
        export_job_id=export_job.id,
        media_id=media_id,
        kind=kind,
        media_storage_path=media.storage_path,
        target_lang=media.target_lang,
    )
    try:
        await redis.rpush(EXPORT_QUEUE_KEY, message.model_dump_json())
    except Exception as exc:
        export_job.status = JobStatus.FAILED.value
        export_job.error_message = f"failed to enqueue export job: {exc}"
        await db.commit()
        await db.refresh(export_job, attribute_names=["updated_at"])
    return export_job


@media_export_router.post("/{media_id}/export/mp3", response_model=ExportJobRead, status_code=201)
async def export_mp3(
    media_id: uuid.UUID,
    accept_long_lines: bool = False,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ExportJob:
    return await _create_export_job(media_id, ExportKind.MP3, db, redis, accept_long_lines)


@media_export_router.post("/{media_id}/export/mp4", response_model=ExportJobRead, status_code=201)
async def export_mp4(
    media_id: uuid.UUID,
    accept_long_lines: bool = False,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ExportJob:
    return await _create_export_job(media_id, ExportKind.MP4, db, redis, accept_long_lines)


@media_export_router.get("/{media_id}/exports", response_model=list[ExportJobRead])
async def list_latest_exports(
    media_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ExportJob]:
    """The most recent export job of each kind, so the page can rebuild its state after a reload."""
    await _load_media_or_404(media_id, db)
    result = await db.execute(
        select(ExportJob)
        .where(ExportJob.media_id == media_id)
        .order_by(ExportJob.created_at.desc(), ExportJob.id)
    )
    latest: dict[str, ExportJob] = {}
    for job in result.scalars().all():
        latest.setdefault(job.kind, job)
    return list(latest.values())


@export_jobs_router.get("/{export_job_id}", response_model=ExportJobRead)
async def get_export_job(export_job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ExportJob:
    export_job = await db.get(ExportJob, export_job_id)
    if export_job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    return export_job


@export_jobs_router.get("/{export_job_id}/download")
async def download_export_job(
    export_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    export_job = await db.get(ExportJob, export_job_id)
    if export_job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    if export_job.status != JobStatus.COMPLETED.value or not export_job.output_path:
        raise HTTPException(status_code=409, detail="Export is not complete yet")

    absolute_path = resolve_stored_file(settings.storage_dir, export_job.output_path)

    is_mp3 = export_job.kind == ExportKind.MP3.value
    media_type = "audio/mpeg" if is_mp3 else "video/mp4"
    extension = "mp3" if is_mp3 else "mp4"
    return FileResponse(
        absolute_path, media_type=media_type, filename=f"dub-{export_job.media_id}.{extension}"
    )
