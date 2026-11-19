import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dubforge_api.config import Settings, get_settings
from dubforge_api.db import get_db
from dubforge_api.models import Artifact as ArtifactModel
from dubforge_api.models import ExportJob, Job, Media, Project
from dubforge_api.models import Segment as SegmentModel
from dubforge_api.schemas import (
    MediaWithJob,
    ProjectCreate,
    ProjectDetailRead,
    ProjectRead,
    rooms_by_segment,
    segment_to_contract,
)
from dubforge_api.storage import remove_stored_dir, remove_stored_file
from dubforge_contracts.models import (
    USABLE_AUDIO_STATUSES,
    JobRead,
    MediaRead,
    SegmentReviewStatus,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)) -> Project:
    project = Project(name=payload.name)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectDetailRead)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ProjectDetailRead:
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.media).selectinload(Media.job),
            selectinload(Project.media).selectinload(Media.segments),
        )
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    segment_ids = [s.id for item in project.media for s in item.segments]
    artifacts_result = await db.execute(
        select(ArtifactModel).where(ArtifactModel.segment_id.in_(segment_ids))
    )
    # Queried directly by FK rather than via the Segment.artifact
    # relationship — see segments.py's _get_artifact_for_segment for why.
    artifact_by_segment_id = {a.segment_id: a for a in artifacts_result.scalars()}

    media = []
    for item in project.media:
        if item.job is None:
            continue
        rooms = rooms_by_segment(list(item.segments))
        segments = [
            segment_to_contract(s, artifact_by_segment_id.get(s.id), rooms.get(s.id))
            for s in item.segments
        ]
        media.append(
            MediaWithJob(
                media=MediaRead.model_validate(item),
                job=JobRead.model_validate(item.job),
                segments=segments,
                approved_count=sum(
                    1
                    for s in item.segments
                    if s.review_status == SegmentReviewStatus.APPROVED.value
                ),
                total_count=len(item.segments),
                usable_audio_count=sum(
                    1 for s in segments if s.audio_status in USABLE_AUDIO_STATUSES
                ),
            )
        )
    return ProjectDetailRead(
        id=project.id, name=project.name, created_at=project.created_at, media=media
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Delete a project with all its media, lines, dubbed audio and exports."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # No ON DELETE CASCADE on these foreign keys, so children go first.
    media_ids = select(Media.id).where(Media.project_id == project_id)
    segment_ids = select(SegmentModel.id).where(SegmentModel.media_id.in_(media_ids))
    audio_paths = (
        (
            await db.execute(
                select(ArtifactModel.audio_path).where(ArtifactModel.segment_id.in_(segment_ids))
            )
        )
        .scalars()
        .all()
    )
    export_paths = (
        (await db.execute(select(ExportJob.output_path).where(ExportJob.media_id.in_(media_ids))))
        .scalars()
        .all()
    )
    await db.execute(delete(ArtifactModel).where(ArtifactModel.segment_id.in_(segment_ids)))
    await db.execute(delete(SegmentModel).where(SegmentModel.media_id.in_(media_ids)))
    await db.execute(delete(ExportJob).where(ExportJob.media_id.in_(media_ids)))
    await db.execute(delete(Job).where(Job.media_id.in_(media_ids)))
    await db.execute(delete(Media).where(Media.project_id == project_id))
    await db.delete(project)
    await db.commit()

    # Files only after the commit, so a failed delete never leaves rows pointing at nothing.
    for path in [*audio_paths, *export_paths]:
        remove_stored_file(settings.storage_dir, path)
    # uploads (and the audio/stems the worker derives next to them) live under the project id
    remove_stored_dir(settings.storage_dir, str(project_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
