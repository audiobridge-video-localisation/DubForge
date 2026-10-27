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
