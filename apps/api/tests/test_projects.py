import uuid
from pathlib import Path
from typing import Any

from httpx import AsyncClient

from dubforge_api.config import get_settings
from dubforge_api.main import app


async def test_create_project(client: AsyncClient) -> None:
    response = await client.post("/projects", json={"name": "My Project"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My Project"
    assert uuid.UUID(body["id"])
    assert "created_at" in body


async def test_list_projects(client: AsyncClient) -> None:
    await client.post("/projects", json={"name": "First"})
    await client.post("/projects", json={"name": "Second"})

    response = await client.get("/projects")

    assert response.status_code == 200
    names = {project["name"] for project in response.json()}
    assert names == {"First", "Second"}


async def test_get_project_found(client: AsyncClient) -> None:
    created = (await client.post("/projects", json={"name": "Findable"})).json()

    response = await client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_project_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404


async def _seed_full_project(client: AsyncClient, storage: Path) -> dict[str, Any]:
    """A project with one uploaded media, a line with dubbed audio and a finished export."""
    project = (await client.post("/projects", json={"name": "Doomed"})).json()
    media_with_job = (
        await client.post(
            f"/projects/{project['id']}/media",
            files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        )
    ).json()
    media_id = media_with_job["media"]["id"]
    await client.patch(
        f"/internal/jobs/{media_with_job['job']['id']}", json={"status": "completed"}
    )
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
                "translated_text": "[hi] Line",
            }
        ],
    )
    segment_id = (await client.get(f"/projects/{project['id']}")).json()["media"][0]["segments"][0][
        "id"
    ]
    await client.post(f"/segments/{segment_id}/approve")

    artifact_id = (await client.post(f"/segments/{segment_id}/regenerate")).json()["id"]
    (storage / "artifacts").mkdir()
    (storage / "artifacts" / f"{artifact_id}.wav").write_bytes(b"dub")
    await client.patch(
        f"/internal/artifacts/{artifact_id}",
        json={
            "status": "completed",
            "audio_path": f"artifacts/{artifact_id}.wav",
            "duration_ms": 1000,
        },
    )

    export_job_id = (await client.post(f"/media/{media_id}/export/mp3")).json()["id"]
    (storage / "exports").mkdir()
    (storage / "exports" / f"{export_job_id}.mp3").write_bytes(b"mp3")
    await client.patch(
        f"/internal/export-jobs/{export_job_id}",
        json={"status": "completed", "output_path": f"exports/{export_job_id}.mp3"},
    )
    return {
        "project_id": project["id"],
        "media_id": media_id,
        "artifact_id": artifact_id,
        "export_job_id": export_job_id,
    }


async def test_delete_project_removes_it_with_everything_in_it(client: AsyncClient) -> None:
    storage = Path(app.dependency_overrides[get_settings]().storage_dir)
    seeded = await _seed_full_project(client, storage)
    keeper = (await client.post("/projects", json={"name": "Keeper"})).json()

    response = await client.delete(f"/projects/{seeded['project_id']}")

    assert response.status_code == 204
    assert (await client.get(f"/projects/{seeded['project_id']}")).status_code == 404
    assert [p["id"] for p in (await client.get("/projects")).json()] == [keeper["id"]]
    assert (await client.get(f"/export-jobs/{seeded['export_job_id']}")).status_code == 404
    assert not (storage / seeded["project_id"]).exists()
    assert not (storage / "artifacts" / f"{seeded['artifact_id']}.wav").exists()
    assert not (storage / "exports" / f"{seeded['export_job_id']}.mp3").exists()


async def test_delete_empty_project(client: AsyncClient) -> None:
    project = (await client.post("/projects", json={"name": "Empty"})).json()

    response = await client.delete(f"/projects/{project['id']}")

    assert response.status_code == 204
    assert (await client.get(f"/projects/{project['id']}")).status_code == 404


async def test_delete_project_not_found(client: AsyncClient) -> None:
    response = await client.delete(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_delete_project_blocked_while_its_job_is_still_running(
    client: AsyncClient,
) -> None:
    project = (await client.post("/projects", json={"name": "Mid-upload"})).json()
    await client.post(
        f"/projects/{project['id']}/media",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    # freshly uploaded media's job is still "pending" - nothing has touched it yet

    response = await client.delete(f"/projects/{project['id']}")

    assert response.status_code == 409
    assert (await client.get(f"/projects/{project['id']}")).status_code == 200


async def test_delete_project_blocked_while_a_line_is_still_regenerating(
    client: AsyncClient,
) -> None:
    project = (await client.post("/projects", json={"name": "Mid-regenerate"})).json()
    media_id = (
        await client.post(
            f"/projects/{project['id']}/media",
            files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        )
    ).json()["media"]["id"]
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
                "translated_text": "[hi] Line",
            }
        ],
    )
    segment_id = (await client.get(f"/projects/{project['id']}")).json()["media"][0]["segments"][0][
        "id"
    ]
    await client.post(f"/segments/{segment_id}/regenerate")
    # the artifact the regenerate created is still "pending" - the worker hasn't called back yet

    response = await client.delete(f"/projects/{project['id']}")

    assert response.status_code == 409


async def test_delete_project_blocked_while_an_export_is_still_running(
    client: AsyncClient,
) -> None:
    seeded = await _seed_full_project(
        client, Path(app.dependency_overrides[get_settings]().storage_dir)
    )
    # _seed_full_project's export job is already completed; start a second one and leave it
    # pending so this test is about the export, not the one _seed_full_project finished.
    await client.post(f"/media/{seeded['media_id']}/export/mp4")

    response = await client.delete(f"/projects/{seeded['project_id']}")

    assert response.status_code == 409


async def test_delete_project_allowed_once_its_job_fails(client: AsyncClient) -> None:
    project = (await client.post("/projects", json={"name": "Failed upload"})).json()
    media_with_job = (
        await client.post(
            f"/projects/{project['id']}/media",
            files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        )
    ).json()
    job_id = media_with_job["job"]["id"]
    await client.patch(f"/internal/jobs/{job_id}", json={"status": "failed"})

    response = await client.delete(f"/projects/{project['id']}")

    assert response.status_code == 204
