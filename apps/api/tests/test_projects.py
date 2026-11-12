import uuid

from httpx import AsyncClient


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
