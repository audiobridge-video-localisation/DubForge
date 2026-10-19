from conftest import FakeRedis
from httpx import AsyncClient


async def test_upload_media_creates_media_and_job(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    project = (await client.post("/projects", json={"name": "Upload Target"})).json()

    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["media"]["filename"] == "clip.mp4"
    assert body["media"]["project_id"] == project["id"]
    assert body["job"]["status"] == "pending"
    assert body["job"]["progress"] == 0
    assert len(fake_redis.calls) == 1
    assert fake_redis.calls[0][0] == "dubforge:jobs"


async def test_upload_media_project_not_found(client: AsyncClient) -> None:
    response = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )

    assert response.status_code == 404


async def test_get_project_includes_media(client: AsyncClient) -> None:
    project = (await client.post("/projects", json={"name": "Detail Target"})).json()
    await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )

    response = await client.get(f"/projects/{project['id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["media"]) == 1
    assert body["media"][0]["media"]["filename"] == "clip.mp4"
