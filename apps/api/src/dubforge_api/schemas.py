import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from dubforge_contracts.models import JobRead, MediaRead, Segment


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class MediaWithJob(BaseModel):
    media: MediaRead
    job: JobRead
    segments: list[Segment] = []
    approved_count: int = 0
    total_count: int = 0


class ProjectDetailRead(ProjectRead):
    media: list[MediaWithJob] = []
