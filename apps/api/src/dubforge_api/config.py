from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[4]
_REPO_ROOT_ENV = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV, extra="ignore")

    database_url: str
    redis_url: str
    storage_dir: str = "./media"

    @field_validator("storage_dir")
    @classmethod
    def _anchor_storage_dir(cls, value: str) -> str:
        path = Path(value)
        return str(path if path.is_absolute() else _REPO_ROOT / path)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
