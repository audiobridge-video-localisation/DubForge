import uuid
from typing import Any

from httpx import AsyncClient


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Edit Target"})).json()
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
                "start_ms": 1000,
                "end_ms": 2000,
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


async def test_patch_segment_updates_text_and_translation(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(
        f"/segments/{segment['id']}",
        json={"text": "Hi there", "translated_text": "[es] Hola"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Hi there"
    assert body["translated_text"] == "[es] Hola"
    assert body["start_ms"] == segment["start_ms"]
    assert body["end_ms"] == segment["end_ms"]


async def test_patch_segment_updates_timestamps_and_recomputes_duration(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(
        f"/segments/{segment['id']}", json={"start_ms": 500, "end_ms": 3000}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["start_ms"] == 500
    assert body["end_ms"] == 3000
    assert body["duration_ms"] == 2500


async def test_patch_segment_rejects_start_after_end_when_both_provided(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(
        f"/segments/{segment['id']}", json={"start_ms": 2000, "end_ms": 1000}
    )

    assert response.status_code == 422


async def test_patch_segment_rejects_start_after_stored_end(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"start_ms": 5000})

    assert response.status_code == 422


async def test_patch_segment_rejects_end_before_stored_start(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"end_ms": 500})

    assert response.status_code == 422


async def test_patch_segment_not_found(client: AsyncClient) -> None:
    response = await client.patch(f"/segments/{uuid.uuid4()}", json={"text": "x"})

    assert response.status_code == 404


async def test_patch_segment_partial_update_leaves_other_fields_untouched(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"text": "Only text"})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Only text"
    assert body["translated_text"] == segment["translated_text"]
    assert body["start_ms"] == segment["start_ms"]
    assert body["end_ms"] == segment["end_ms"]
    assert body["duration_ms"] == segment["duration_ms"]
