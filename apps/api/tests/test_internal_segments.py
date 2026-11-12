import uuid
from pathlib import Path
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dubforge_api.config import get_settings
from dubforge_api.main import app


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Segment Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


def _segment_payload(index: int, text: str) -> dict[str, Any]:
    return {
        "index": index,
        "start_ms": index * 1000,
        "end_ms": index * 1000 + 1000,
        "duration_ms": 1000,
        "speaker_label": f"Speaker {index}",
        "text": text,
    }


async def test_replace_segments_creates_ordered_segments(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]

    response = await client.put(
        f"/internal/media/{media_id}/segments",
        json=[_segment_payload(0, "First"), _segment_payload(1, "Second")],
    )

    assert response.status_code == 204

    project_id = media_with_job["media"]["project_id"]
    detail = (await client.get(f"/projects/{project_id}")).json()
    segments = detail["media"][0]["segments"]
    assert [s["text"] for s in segments] == ["First", "Second"]
    assert [s["index"] for s in segments] == [0, 1]


async def test_replace_segments_replaces_not_appends(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]

    await client.put(f"/internal/media/{media_id}/segments", json=[_segment_payload(0, "Old")])
    await client.put(f"/internal/media/{media_id}/segments", json=[_segment_payload(0, "New")])

    project_id = media_with_job["media"]["project_id"]
    detail = (await client.get(f"/projects/{project_id}")).json()
    segments = detail["media"][0]["segments"]
    assert [s["text"] for s in segments] == ["New"]


async def test_replace_segments_media_not_found(client: AsyncClient) -> None:
    response = await client.put(
        f"/internal/media/{uuid.uuid4()}/segments", json=[_segment_payload(0, "Text")]
    )

    assert response.status_code == 404


async def test_upload_media_has_no_segments_yet(client: AsyncClient) -> None:
    media_with_job = await _upload(client)

    assert media_with_job["segments"] == []


async def test_replace_segments_after_audio_exists_drops_the_old_audio(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]
    project_id = media_with_job["media"]["project_id"]
    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[{**_segment_payload(0, "Old"), "translated_text": "Vieux"}],
    )
    old = (await client.get(f"/projects/{project_id}")).json()["media"][0]["segments"][0]

    audio = Path(app.dependency_overrides[get_settings]().storage_dir) / "artifacts" / "old.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"RIFF")
    artifact_id = (await client.post(f"/segments/{old['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "artifacts/old.wav", "duration_ms": 1000},
    )
    await client.post(f"/segments/{old['id']}/approve")
    await client.post(f"/media/{media_id}/ready-for-dubbing")

    response = await client.put(
        f"/internal/media/{media_id}/segments",
        json=[{**_segment_payload(0, "New"), "translated_text": "Nouveau"}],
    )

    assert response.status_code == 204  # used to be a 500 (foreign key from the old audio)
    detail = (await client.get(f"/projects/{project_id}")).json()["media"][0]
    assert [s["text"] for s in detail["segments"]] == ["New"]
    assert detail["segments"][0]["artifact"] is None
    assert detail["segments"][0]["audio_status"] == "no_audio"
    assert detail["media"]["ready_for_dubbing"] is False
    assert not audio.exists()  # the orphaned file is cleaned up too
