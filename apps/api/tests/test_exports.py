import uuid
from pathlib import Path
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient

from dubforge_api.config import get_settings
from dubforge_api.main import app


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Export Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


async def _seed_segments(client: AsyncClient, count: int = 2) -> dict[str, Any]:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]

    segments = [
        {
            "index": i,
            "start_ms": i * 1000,
            "end_ms": (i + 1) * 1000,
            "duration_ms": 1000,
            "speaker_label": f"Speaker {i}",
            "text": f"Line {i}",
            "translated_text": f"[es] Line {i}",
        }
        for i in range(count)
    ]
    await client.put(f"/internal/media/{media_id}/segments", json=segments)

    project_id = media_with_job["media"]["project_id"]
    detail = (await client.get(f"/projects/{project_id}")).json()
    media_with_job["segments"] = detail["media"][0]["segments"]
    return media_with_job


async def _make_fully_ready(client: AsyncClient, media_with_job: dict[str, Any]) -> None:
    for segment in media_with_job["segments"]:
        await client.post(f"/segments/{segment['id']}/approve")
        artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
        await client.patch(
            f"/internal/artifacts/{artifact_id}",
            json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 1000},
        )


async def test_export_srt_returns_subrip_body(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=2)
    media_id = media_with_job["media"]["id"]

    response = await client.get(f"/media/{media_id}/export/srt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-subrip")
    assert "[es] Line 0" in response.text
    assert "[es] Line 1" in response.text
    assert "00:00:00,000 --> 00:00:01,000" in response.text


async def test_export_vtt_returns_webvtt_body(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=1)
    media_id = media_with_job["media"]["id"]

    response = await client.get(f"/media/{media_id}/export/vtt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vtt")
    assert response.text.startswith("WEBVTT")
    assert "[es] Line 0" in response.text


async def test_export_srt_no_segments_conflicts(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]

    response = await client.get(f"/media/{media_id}/export/srt")

    assert response.status_code == 409


async def test_export_srt_media_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/media/{uuid.uuid4()}/export/srt")

    assert response.status_code == 404


async def test_export_mp3_requires_full_readiness(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    media_with_job = await _seed_segments(client, count=2)
    media_id = media_with_job["media"]["id"]

    response = await client.post(f"/media/{media_id}/export/mp3")
    assert response.status_code == 409

    for segment in media_with_job["segments"]:
        await client.post(f"/segments/{segment['id']}/approve")
    response = await client.post(f"/media/{media_id}/export/mp3")
    assert response.status_code == 409

    await _make_fully_ready(client, media_with_job)
    response = await client.post(f"/media/{media_id}/export/mp3")

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "mp3"
    assert body["status"] == "pending"
    export_calls = [c for c in fake_redis.calls if c[0] == "dubforge:exports"]
    assert len(export_calls) == 1


async def test_export_mp4_requires_full_readiness(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    media_with_job = await _seed_segments(client, count=1)
    media_id = media_with_job["media"]["id"]

    response = await client.post(f"/media/{media_id}/export/mp4")
    assert response.status_code == 409

    await _make_fully_ready(client, media_with_job)
    response = await client.post(f"/media/{media_id}/export/mp4")

    assert response.status_code == 201
    assert response.json()["kind"] == "mp4"
    export_calls = [c for c in fake_redis.calls if c[0] == "dubforge:exports"]
    assert len(export_calls) == 1


async def test_get_export_job_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/export-jobs/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_update_export_job_internal(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    export_job_id = (
        await client.post(f"/media/{media_with_job['media']['id']}/export/mp3")
    ).json()["id"]

    response = await client.patch(
        f"/internal/export-jobs/{export_job_id}",
        json={"status": "completed", "progress": 100, "output_path": "exports/x.mp3"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["output_path"] == "exports/x.mp3"


async def test_update_export_job_truncates_long_error_message(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    export_job_id = (
        await client.post(f"/media/{media_with_job['media']['id']}/export/mp3")
    ).json()["id"]

    response = await client.patch(
        f"/internal/export-jobs/{export_job_id}",
        json={"status": "failed", "error_message": "x" * 3000},
    )

    assert response.status_code == 200
    assert len(response.json()["error_message"]) == 2000


async def test_update_export_job_not_found(client: AsyncClient) -> None:
    response = await client.patch(
        f"/internal/export-jobs/{uuid.uuid4()}", json={"status": "completed"}
    )

    assert response.status_code == 404


async def test_download_export_job_not_completed_conflicts(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    export_job_id = (
        await client.post(f"/media/{media_with_job['media']['id']}/export/mp3")
    ).json()["id"]

    response = await client.get(f"/export-jobs/{export_job_id}/download")

    assert response.status_code == 409


async def test_download_export_job_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/export-jobs/{uuid.uuid4()}/download")

    assert response.status_code == 404


async def test_download_export_job_completed_serves_file(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    export_job_id = (
        await client.post(f"/media/{media_with_job['media']['id']}/export/mp3")
    ).json()["id"]

    settings = app.dependency_overrides[get_settings]()
    output_path = Path(settings.storage_dir) / "exports" / f"{export_job_id}.mp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp3 bytes")

    await client.patch(
        f"/internal/export-jobs/{export_job_id}",
        json={
            "status": "completed",
            "progress": 100,
            "output_path": f"exports/{export_job_id}.mp3",
        },
    )

    response = await client.get(f"/export-jobs/{export_job_id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake mp3 bytes"


async def test_internal_list_media_segments(client: AsyncClient) -> None:
    media_with_job = await _seed_segments(client, count=2)
    media_id = media_with_job["media"]["id"]

    response = await client.get(f"/internal/media/{media_id}/segments")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["index"] == 0
    assert body[0]["text"] == "Line 0"


async def test_internal_list_media_segments_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/internal/media/{uuid.uuid4()}/segments")

    assert response.status_code == 404
