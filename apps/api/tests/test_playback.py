from pathlib import Path
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient

from dubforge_api.config import get_settings
from dubforge_api.main import app


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Playback"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"video-bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


async def _seed_segment(client: AsyncClient) -> tuple[str, str]:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]
    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[
            {
                "index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "duration_ms": 1000,
                "speaker_label": "Speaker 0",
                "text": "Line",
                "translated_text": "[es] Line",
            }
        ],
    )
    project_id = media_with_job["media"]["project_id"]
    detail = (await client.get(f"/projects/{project_id}")).json()
    return media_id, detail["media"][0]["segments"][0]["id"]


def _storage_dir() -> Path:
    return Path(app.dependency_overrides[get_settings]().storage_dir)


async def test_source_media_is_served_inline_with_its_type(client: AsyncClient) -> None:
    media_id, _ = await _seed_segment(client)

    response = await client.get(f"/media/{media_id}/source")

    assert response.status_code == 200
    assert response.content == b"video-bytes"
    assert response.headers["content-type"] == "video/mp4"


async def test_source_media_supports_range_requests(client: AsyncClient) -> None:
    media_id, _ = await _seed_segment(client)

    response = await client.get(f"/media/{media_id}/source", headers={"Range": "bytes=0-4"})

    assert response.status_code == 206
    assert response.content == b"video"


async def test_source_media_not_found(client: AsyncClient) -> None:
    response = await client.get("/media/00000000-0000-0000-0000-000000000000/source")

    assert response.status_code == 404


async def test_source_media_missing_on_disk(client: AsyncClient) -> None:
    media_id, _ = await _seed_segment(client)
    for path in _storage_dir().rglob("*.mp4"):
        path.unlink()

    response = await client.get(f"/media/{media_id}/source")

    assert response.status_code == 404


async def test_segment_audio_served_when_completed(client: AsyncClient) -> None:
    _, segment_id = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment_id}/regenerate")).json()["id"]
    (_storage_dir() / "dub.wav").write_bytes(b"RIFFwav")
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "dub.wav", "duration_ms": 1000},
    )

    response = await client.get(f"/segments/{segment_id}/audio")

    assert response.status_code == 200
    assert response.content == b"RIFFwav"
    assert response.headers["content-type"] == "audio/wav"


async def test_segment_audio_conflict_without_completed_artifact(client: AsyncClient) -> None:
    _, segment_id = await _seed_segment(client)

    assert (await client.get(f"/segments/{segment_id}/audio")).status_code == 409

    await client.post(f"/segments/{segment_id}/regenerate")  # pending artifact
    assert (await client.get(f"/segments/{segment_id}/audio")).status_code == 409


async def test_segment_audio_refuses_paths_outside_storage(client: AsyncClient) -> None:
    _, segment_id = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment_id}/regenerate")).json()["id"]
    outside = _storage_dir().parent / "secret.wav"
    outside.write_bytes(b"secret")
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "../secret.wav", "duration_ms": 1000},
    )

    response = await client.get(f"/segments/{segment_id}/audio")

    assert response.status_code == 404
    assert b"secret" not in response.content


async def test_segment_audio_not_found(client: AsyncClient) -> None:
    response = await client.get("/segments/00000000-0000-0000-0000-000000000000/audio")

    assert response.status_code == 404


async def test_regenerate_refuses_a_blank_translation(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    _, segment_id = await _seed_segment(client)
    await client.patch(f"/segments/{segment_id}", json={"translated_text": "  "})
    queued_before = len(fake_redis.calls)

    response = await client.post(f"/segments/{segment_id}/regenerate")

    assert response.status_code == 409
    assert "translation" in response.json()["detail"]
    assert len(fake_redis.calls) == queued_before
