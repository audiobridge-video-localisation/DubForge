from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import get_settings
from dubforge_api.db import Base, engine, get_db
from dubforge_api.main import app
from dubforge_api.redis_client import get_redis


@pytest.fixture(autouse=True, scope="session")
async def _create_schema() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def _override_get_db() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_db] = _override_get_db
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await transaction.rollback()


class FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def rpush(self, key: str, value: str) -> None:
        self.calls.append((key, value))


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(autouse=True)
def _override_redis(fake_redis: FakeRedis) -> Iterator[None]:
    app.dependency_overrides[get_redis] = lambda: fake_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture(autouse=True)
def _override_storage_dir(tmp_path: Path) -> Iterator[None]:
    settings = get_settings().model_copy(update={"storage_dir": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
