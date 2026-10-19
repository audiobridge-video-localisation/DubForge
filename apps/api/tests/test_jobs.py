import uuid
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Job Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


async def test_get_job(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    job_id = media_with_job["job"]["id"]

    response = await client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_get_job_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/jobs/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_internal_update_job(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    job_id = media_with_job["job"]["id"]

    response = await client.patch(
        f"/internal/jobs/{job_id}", json={"status": "processing", "progress": 40}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert body["progress"] == 40


async def test_internal_update_job_truncates_long_error_message(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    job_id = media_with_job["job"]["id"]

    response = await client.patch(
        f"/internal/jobs/{job_id}",
        json={"status": "failed", "error_message": "x" * 3000},
    )

    assert response.status_code == 200
    assert len(response.json()["error_message"]) == 2000


async def test_internal_update_job_not_found(client: AsyncClient) -> None:
    response = await client.patch(f"/internal/jobs/{uuid.uuid4()}", json={"status": "completed"})

    assert response.status_code == 404


async def test_retry_job(client: AsyncClient, fake_redis: FakeRedis) -> None:
    media_with_job = await _upload(client)
    job_id = media_with_job["job"]["id"]
    await client.patch(
        f"/internal/jobs/{job_id}", json={"status": "failed", "error_message": "boom"}
    )

    response = await client.post(f"/jobs/{job_id}/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["progress"] == 0
    assert body["error_message"] is None
    assert body["retry_count"] == 1
    assert len(fake_redis.calls) == 2


async def test_retry_non_failed_job_conflicts(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    job_id = media_with_job["job"]["id"]

    response = await client.post(f"/jobs/{job_id}/retry")

    assert response.status_code == 409
