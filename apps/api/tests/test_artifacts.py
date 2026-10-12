import uuid
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Artifact Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


async def _seed_segment(client: AsyncClient) -> dict[str, Any]:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]
    project_id = media_with_job["media"]["project_id"]

    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[
            {
                "index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "duration_ms": 1000,
                "speaker_label": "Speaker 0",
                "text": "Hello",
                "translated_text": "[es] Hello",
            }
        ],
    )

    detail = (await client.get(f"/projects/{project_id}")).json()
    segment: dict[str, Any] = detail["media"][0]["segments"][0]
    return segment


async def test_regenerate_creates_artifact_and_queues_message(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    segment = await _seed_segment(client)

    response = await client.post(f"/segments/{segment['id']}/regenerate")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["retry_count"] == 0
    artifact_calls = [c for c in fake_redis.calls if c[0] == "dubforge:artifacts"]
    assert len(artifact_calls) == 1


async def test_regenerate_again_resets_and_increments_retry_count(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]

    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "failed", "error_message": "boom"},
    )

    response = await client.post(f"/segments/{segment['id']}/regenerate")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["error_message"] is None
    assert body["retry_count"] == 1
    artifact_calls = [c for c in fake_redis.calls if c[0] == "dubforge:artifacts"]
    assert len(artifact_calls) == 2


async def test_regenerate_not_found(client: AsyncClient) -> None:
    response = await client.post(f"/segments/{uuid.uuid4()}/regenerate")

    assert response.status_code == 404


async def test_internal_update_artifact(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]

    response = await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 2000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["audio_path"] == "/tmp/dub.wav"
    assert body["duration_ms"] == 2000


async def test_internal_update_artifact_not_found(client: AsyncClient) -> None:
    response = await client.patch(
        f"/internal/artifacts/{uuid.uuid4()}", json={"status": "completed"}
    )

    assert response.status_code == 404


async def test_editing_segment_with_completed_artifact_marks_it_outdated(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 2000},
    )

    response = await client.patch(f"/segments/{segment['id']}", json={"text": "Edited"})

    assert response.status_code == 200
    assert response.json()["artifact"]["status"] == "outdated"


async def test_editing_segment_without_artifact_is_a_no_op(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"text": "Edited"})

    assert response.status_code == 200
    assert response.json()["artifact"] is None


async def test_project_detail_includes_nested_artifact(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]
    project_id = media_with_job["media"]["project_id"]
    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[
            {
                "index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "duration_ms": 1000,
                "speaker_label": "Speaker 0",
                "text": "Hello",
                "translated_text": "[es] Hello",
            }
        ],
    )
    detail = (await client.get(f"/projects/{project_id}")).json()
    segment = detail["media"][0]["segments"][0]
    await client.post(f"/segments/{segment['id']}/regenerate")

    detail = (await client.get(f"/projects/{project_id}")).json()
    artifact = detail["media"][0]["segments"][0]["artifact"]

    assert artifact is not None
    assert artifact["status"] == "pending"
