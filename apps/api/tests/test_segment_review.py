import uuid
from typing import Any

from httpx import AsyncClient


async def _upload(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Review Target"})).json()
    response = await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    result: dict[str, Any] = response.json()
    return result


def _segment_payload(index: int) -> dict[str, Any]:
    return {
        "index": index,
        "start_ms": index * 1000,
        "end_ms": index * 1000 + 1000,
        "duration_ms": 1000,
        "speaker_label": f"Speaker {index}",
        "text": f"Line {index}",
        "translated_text": f"[es] Line {index}",
    }


async def _seed_segments(client: AsyncClient, count: int) -> tuple[str, str, list[dict[str, Any]]]:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]
    project_id = media_with_job["media"]["project_id"]

    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[_segment_payload(i) for i in range(count)],
    )

    detail = (await client.get(f"/projects/{project_id}")).json()
    segments: list[dict[str, Any]] = detail["media"][0]["segments"]
    return project_id, media_id, segments


async def _seed_segment(client: AsyncClient) -> dict[str, Any]:
    _, _, segments = await _seed_segments(client, 1)
    return segments[0]


async def test_patch_segment_corrects_speaker_label(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"speaker_label": "Dr. Smith"})

    assert response.status_code == 200
    assert response.json()["speaker_label"] == "Dr. Smith"


async def test_new_segment_starts_pending(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    assert segment["review_status"] == "pending"


async def test_approve_segment(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.post(f"/segments/{segment['id']}/approve")

    assert response.status_code == 200
    assert response.json()["review_status"] == "approved"


async def test_request_changes_segment(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.post(f"/segments/{segment['id']}/request-changes")

    assert response.status_code == 200
    assert response.json()["review_status"] == "needs_changes"


async def test_approve_not_found(client: AsyncClient) -> None:
    response = await client.post(f"/segments/{uuid.uuid4()}/approve")

    assert response.status_code == 404


async def test_editing_approved_segment_reverts_to_pending(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/approve")

    response = await client.patch(f"/segments/{segment['id']}", json={"text": "Edited"})

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending"


async def test_editing_needs_changes_segment_reverts_to_pending(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/request-changes")

    response = await client.patch(f"/segments/{segment['id']}", json={"speaker_label": "X"})

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending"


async def test_patch_without_content_change_does_not_touch_approved_status(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/approve")

    response = await client.patch(f"/segments/{segment['id']}", json={})

    assert response.status_code == 200
    assert response.json()["review_status"] == "approved"


async def test_project_detail_reports_review_progress(client: AsyncClient) -> None:
    project_id, _media_id, segments = await _seed_segments(client, 3)
    await client.post(f"/segments/{segments[0]['id']}/approve")
    await client.post(f"/segments/{segments[1]['id']}/approve")

    detail = (await client.get(f"/projects/{project_id}")).json()
    media_item = detail["media"][0]

    assert media_item["approved_count"] == 2
    assert media_item["total_count"] == 3


async def test_ready_for_dubbing_rejected_when_not_all_approved(client: AsyncClient) -> None:
    _project_id, media_id, segments = await _seed_segments(client, 2)
    await client.post(f"/segments/{segments[0]['id']}/approve")

    response = await client.post(f"/media/{media_id}/ready-for-dubbing")

    assert response.status_code == 409


async def test_ready_for_dubbing_rejected_with_zero_segments(client: AsyncClient) -> None:
    media_with_job = await _upload(client)
    media_id = media_with_job["media"]["id"]

    response = await client.post(f"/media/{media_id}/ready-for-dubbing")

    assert response.status_code == 409


async def test_ready_for_dubbing_succeeds_when_all_approved(client: AsyncClient) -> None:
    project_id, media_id, segments = await _seed_segments(client, 2)
    for segment in segments:
        await client.post(f"/segments/{segment['id']}/approve")

    response = await client.post(f"/media/{media_id}/ready-for-dubbing")

    assert response.status_code == 200
    assert response.json()["ready_for_dubbing"] is True

    detail = (await client.get(f"/projects/{project_id}")).json()
    assert detail["media"][0]["media"]["ready_for_dubbing"] is True


async def test_ready_for_dubbing_not_found(client: AsyncClient) -> None:
    response = await client.post(f"/media/{uuid.uuid4()}/ready-for-dubbing")

    assert response.status_code == 404
