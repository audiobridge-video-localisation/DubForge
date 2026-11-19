import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import get_settings
from dubforge_api.main import app
from dubforge_api.models import ExportJob


async def _upload(client: AsyncClient, target_lang: str | None = None) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Export Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        data={"target_lang": target_lang} if target_lang else None,
    )
    result: dict[str, Any] = response.json()
    return result


async def _seed_segments(
    client: AsyncClient, count: int = 2, target_lang: str | None = None
) -> dict[str, Any]:
    media_with_job = await _upload(client, target_lang)
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


async def test_export_queues_the_media_target_lang(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    media_with_job = await _seed_segments(client, count=1, target_lang="bn")
    media_id = media_with_job["media"]["id"]
    await _make_fully_ready(client, media_with_job)

    response = await client.post(f"/media/{media_id}/export/mp3")

    assert response.status_code == 201
    export_calls = [c for c in fake_redis.calls if c[0] == "dubforge:exports"]
    queued = json.loads(export_calls[-1][1])
    assert queued["target_lang"] == "bn"


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


async def test_export_anyway_lets_only_long_lines_through(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    media_with_job = await _seed_segments(client, count=1)
    media_id = media_with_job["media"]["id"]
    segment_id = media_with_job["segments"][0]["id"]

    # approved, but no audio yet: "export anyway" does not skip that
    await client.post(f"/segments/{segment_id}/approve")
    response = await client.post(f"/media/{media_id}/export/mp4?accept_long_lines=true")
    assert response.status_code == 409

    # 3000ms in a 1000ms slot: too long even for the slowed video
    artifact_id = (await client.post(f"/segments/{segment_id}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 3000},
    )
    await client.post(f"/segments/{segment_id}/approve")
    assert (await client.post(f"/media/{media_id}/export/mp4")).status_code == 409

    response = await client.post(f"/media/{media_id}/export/mp4?accept_long_lines=true")
    assert response.status_code == 201
    assert len([c for c in fake_redis.calls if c[0] == "dubforge:exports"]) == 1


async def test_list_exports_empty_before_any_export(client: AsyncClient) -> None:
    media_with_job = await _upload(client)

    response = await client.get(f"/media/{media_with_job['media']['id']}/exports")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_exports_returns_latest_job_of_each_kind(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    media_id = media_with_job["media"]["id"]

    first_mp3 = (await client.post(f"/media/{media_id}/export/mp3")).json()["id"]
    await client.patch(f"/internal/export-jobs/{first_mp3}", json={"status": "failed"})
    second_mp3 = (await client.post(f"/media/{media_id}/export/mp3")).json()["id"]
    mp4 = (await client.post(f"/media/{media_id}/export/mp4")).json()["id"]
    # the test session is one transaction, so every row got the same now(); age the first
    # retry so "latest" is unambiguous, as it is when each request commits on its own
    first = await db_session.get(ExportJob, uuid.UUID(first_mp3))
    assert first is not None
    first.created_at = datetime(2020, 1, 1, tzinfo=UTC)
    await db_session.flush()

    response = await client.get(f"/media/{media_id}/exports")

    assert response.status_code == 200
    by_kind = {job["kind"]: job["id"] for job in response.json()}
    assert by_kind == {"mp3": second_mp3, "mp4": mp4}


async def test_list_exports_media_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/media/{uuid.uuid4()}/exports")

    assert response.status_code == 404


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


async def test_download_export_refuses_a_path_outside_storage(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    media_with_job = await _seed_segments(client, count=1)
    await _make_fully_ready(client, media_with_job)
    export_job_id = (
        await client.post(f"/media/{media_with_job['media']['id']}/export/mp3")
    ).json()["id"]
    outside = (
        Path(app.dependency_overrides[get_settings]().storage_dir).parent / "outside-secret.txt"
    )
    outside.write_text("secret")
    try:
        await client.patch(
            f"/internal/export-jobs/{export_job_id}",
            json={"status": "completed", "output_path": "../outside-secret.txt"},
        )

        response = await client.get(f"/export-jobs/{export_job_id}/download")

        assert response.status_code == 404
        assert b"secret" not in response.content
    finally:
        outside.unlink(missing_ok=True)
