from fastapi import FastAPI

app = FastAPI(title="DubForge API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run("dubforge_api.main:app", host="0.0.0.0", port=8000)
