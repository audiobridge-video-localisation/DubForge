from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dubforge_api.routers import projects

app = FastAPI(title="DubForge API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run("dubforge_api.main:app", host="0.0.0.0", port=8000)
