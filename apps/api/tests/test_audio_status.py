from typing import Any

from httpx import AsyncClient


async def _seed_segment(client: AsyncClient, duration_ms: int = 1000) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Audio Status Target"})).json()
    media_with_job = (
        await client.post(
            f"/projects/{project['id']}/media",
            files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        )
    ).json()
    media_id = media_with_job["media"]["id"]

    await client.put(
        f"/internal/media/{media_id}/segments",
        json=[
            {
                "index": 0,
                "start_ms": 0,
                "end_ms": duration_ms,
                "duration_ms": duration_ms,
                "speaker_label": "Speaker 0",
                "text": "Hello",
                "translated_text": "[es] Hello",
            }
        ],
    )

    detail = (await client.get(f"/projects/{project['id']}")).json()
    segment: dict[str, Any] = detail["media"][0]["segments"][0]
    segment["_project_id"] = project["id"]
    return segment


async def test_no_artifact_is_no_audio(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    assert segment["audio_status"] == "no_audio"


async def test_pending_artifact_is_pending(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/regenerate")

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    assert detail["media"][0]["segments"][0]["audio_status"] == "pending"


async def test_failed_artifact_is_failed(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}", json={"status": "failed", "error_message": "boom"}
    )

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    assert detail["media"][0]["segments"][0]["audio_status"] == "failed"


async def test_outdated_artifact_is_outdated(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 1000},
    )

    await client.patch(f"/segments/{segment['id']}", json={"text": "Edited"})

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    assert detail["media"][0]["segments"][0]["audio_status"] == "outdated"


async def test_completed_within_tolerance_is_ready(client: AsyncClient) -> None:
    segment = await _seed_segment(client, duration_ms=1000)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 1050},
    )

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    assert detail["media"][0]["segments"][0]["audio_status"] == "ready"


async def test_completed_much_shorter_than_slot_is_ready(client: AsyncClient) -> None:
    segment = await _seed_segment(client, duration_ms=2000)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 400},
    )

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    media = detail["media"][0]
    assert media["segments"][0]["audio_status"] == "ready"
    assert media["usable_audio_count"] == 1


async def test_completed_far_off_duration_is_mismatch(client: AsyncClient) -> None:
    segment = await _seed_segment(client, duration_ms=1000)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 2200},
    )

    detail = (await client.get(f"/projects/{segment['_project_id']}")).json()
    assert detail["media"][0]["segments"][0]["audio_status"] == "mismatch"


async def test_usable_audio_count_reflects_only_ready_segments(client: AsyncClient) -> None:
    segment = await _seed_segment(client, duration_ms=1000)
    project_id = segment["_project_id"]
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 1050},
    )

    detail = (await client.get(f"/projects/{project_id}")).json()
    media = detail["media"][0]
    assert media["usable_audio_count"] == 1
    assert media["total_count"] == 1

    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "audio_path": "/tmp/dub.wav", "duration_ms": 9000},
    )

    detail = (await client.get(f"/projects/{project_id}")).json()
    media = detail["media"][0]
    assert media["usable_audio_count"] == 0
