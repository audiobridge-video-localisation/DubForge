import json
from typing import Any

from conftest import FakeRedis
from httpx import AsyncClient


async def _seed_segment(client: AsyncClient) -> dict[str, Any]:
    project = (await client.post("/projects", json={"name": "Shortening Target"})).json()
    media = (
        await client.post(
            f"/projects/{project['id']}/media",
            files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        )
    ).json()
    await client.put(
        f"/internal/media/{media['media']['id']}/segments",
        json=[
            {
                "index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "duration_ms": 1000,
                "speaker_label": "Speaker 0",
                "text": "Hello there",
                "translated_text": "a very long wording",
            }
        ],
    )
    detail = (await client.get(f"/projects/{project['id']}")).json()
    segment: dict[str, Any] = detail["media"][0]["segments"][0]
    segment["_project_id"] = project["id"]
    return segment


async def _segment(client: AsyncClient, seed: dict[str, Any]) -> dict[str, Any]:
    detail = (await client.get(f"/projects/{seed['_project_id']}")).json()
    segment: dict[str, Any] = detail["media"][0]["segments"][0]
    return segment


async def test_a_new_translation_comes_from_the_machine(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    assert segment["translation_source"] == "machine"


async def test_editing_the_translation_marks_it_as_edited(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(
        f"/segments/{segment['id']}", json={"translated_text": "my own wording"}
    )

    assert response.json()["translation_source"] == "edited"


async def test_editing_something_else_keeps_the_source(client: AsyncClient) -> None:
    segment = await _seed_segment(client)

    response = await client.patch(f"/segments/{segment['id']}", json={"speaker_label": "Anna"})

    assert response.json()["translation_source"] == "machine"


async def test_regenerate_lets_the_worker_rewrite_only_untouched_lines(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    segment = await _seed_segment(client)

    before = len(fake_redis.calls)
    await client.post(f"/segments/{segment['id']}/regenerate")
    machine = json.loads(fake_redis.calls[before][1])

    await client.patch(f"/segments/{segment['id']}", json={"translated_text": "mine"})
    before = len(fake_redis.calls)
    await client.post(f"/segments/{segment['id']}/regenerate")
    edited = json.loads(fake_redis.calls[before][1])

    assert machine["may_rewrite"] is True and machine["source_text"] == "Hello there"
    assert edited["may_rewrite"] is False


async def test_a_shortened_wording_from_the_worker_is_adopted_and_needs_review(
    client: AsyncClient,
) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/approve")
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]

    response = await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={
            "status": "completed",
            "audio_path": "x.wav",
            "duration_ms": 1000,
            "translated_text": "short",
        },
    )

    assert response.status_code == 200
    after = await _segment(client, segment)
    assert after["translated_text"] == "short"
    assert after["translation_source"] == "auto_shortened"
    assert after["review_status"] == "pending"  # an approval of the old wording no longer applies
    assert after["audio_status"] == "ready"


async def test_the_same_wording_changes_nothing(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    await client.post(f"/segments/{segment['id']}/approve")
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]

    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "duration_ms": 1000, "translated_text": "a very long wording"},
    )

    after = await _segment(client, segment)
    assert after["translation_source"] == "machine" and after["review_status"] == "approved"


async def test_a_person_who_edits_meanwhile_keeps_their_text(client: AsyncClient) -> None:
    segment = await _seed_segment(client)
    artifact_id = (await client.post(f"/segments/{segment['id']}/regenerate")).json()["id"]
    await client.patch(f"/segments/{segment['id']}", json={"translated_text": "mine"})

    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={"status": "completed", "duration_ms": 1000, "translated_text": "worker wording"},
    )

    after = await _segment(client, segment)
    assert after["translated_text"] == "mine"
    assert after["translation_source"] == "edited"
    assert after["audio_status"] == "outdated"  # the audio says the worker's wording, not theirs
