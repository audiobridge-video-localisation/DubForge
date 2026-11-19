import shutil
from pathlib import Path

from fastapi import HTTPException


def resolve_stored_file(storage_dir: str, relative_path: str) -> Path:
    """Absolute path of a stored file, refusing anything outside the storage directory."""
    root = Path(storage_dir).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=404, detail="File not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File is missing on disk")
    return path


def remove_stored_file(storage_dir: str, relative_path: str | None) -> None:
    """Best-effort delete of a file the database no longer refers to."""
    if not relative_path:
        return
    root = Path(storage_dir).resolve()
    path = (root / relative_path).resolve()
    if path.is_relative_to(root):
        path.unlink(missing_ok=True)


def remove_stored_dir(storage_dir: str, relative_path: str) -> None:
    """Best-effort delete of a directory under storage, never the storage root itself."""
    root = Path(storage_dir).resolve()
    path = (root / relative_path).resolve()
    if path != root and path.is_relative_to(root):
        shutil.rmtree(path, ignore_errors=True)
