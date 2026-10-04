import uuid
from typing import Any

from httpx import AsyncClient


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
