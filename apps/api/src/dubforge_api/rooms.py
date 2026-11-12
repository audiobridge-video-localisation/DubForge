import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.models import Segment as SegmentModel
from dubforge_api.schemas import rooms_by_segment


async def media_rooms(db: AsyncSession, media_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Room (see dubforge_contracts.segment_room_ms) of every segment of one media."""
    result = await db.execute(select(SegmentModel).where(SegmentModel.media_id == media_id))
    return rooms_by_segment(list(result.scalars().all()))
