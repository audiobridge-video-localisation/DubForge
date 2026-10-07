import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dubforge_api.db import get_db
from dubforge_api.models import Media, Project
from dubforge_api.schemas import MediaWithJob, ProjectCreate, ProjectDetailRead, ProjectRead
from dubforge_contracts.models import JobRead, MediaRead, Segment

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

    media = [
        MediaWithJob(
            media=MediaRead.model_validate(item),
            job=JobRead.model_validate(item.job),
            segments=[Segment.model_validate(s) for s in item.segments],
        )
        for item in project.media
        if item.job is not None
    ]
    return ProjectDetailRead(
        id=project.id, name=project.name, created_at=project.created_at, media=media
    )
