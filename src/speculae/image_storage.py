"""
File-based image storage for Speculae.

Images live under ``{data_dir}/images/YYYY/MM/{entry_id}/{image_id}.ext``.
The database stores only metadata and a relative ``storage_path`` — never BLOBs.

Layout rationale:
  - Year/month sharding keeps directories bounded for backup and filesystem browse.
  - Per-entry subfolders make cascade delete O(1) directory removal.
  - Image id in the filename prevents collisions and maps 1:1 to DB rows.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

MIME_EXTENSIONS: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def images_root(data_dir: Path) -> Path:
    """Canonical root for all journal images."""
    return data_dir / "images"


def extension_for(mime_type: str, filename: str) -> str:
    """Pick a stable file extension from MIME type, falling back to filename."""
    ext = MIME_EXTENSIONS.get(mime_type.lower().strip())
    if ext:
        return ext
    suffix = Path(filename).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    return ".bin"


def build_relative_path(
    entry_date: date,
    entry_id: str,
    image_id: str,
    mime_type: str,
    filename: str,
) -> str:
    """Build a DB-safe relative path under the images root."""
    ext = extension_for(mime_type, filename)
    return f"{entry_date.year:04d}/{entry_date.month:02d}/{entry_id}/{image_id}{ext}"


def resolve_path(data_dir: Path, relative_path: str) -> Path:
    """Resolve a stored relative path, rejecting traversal outside images root."""
    root = images_root(data_dir).resolve()
    full = (root / relative_path).resolve()
    if root not in full.parents and full != root:
        raise ValueError(f"Invalid storage path: {relative_path!r}")
    return full


def write_file(data_dir: Path, relative_path: str, data: bytes) -> Path:
    """Persist image bytes to disk. Creates parent directories as needed."""
    path = resolve_path(data_dir, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def read_file(data_dir: Path, relative_path: str) -> bytes:
    """Load image bytes from disk."""
    path = resolve_path(data_dir, relative_path)
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return path.read_bytes()


def file_exists(data_dir: Path, relative_path: str) -> bool:
    try:
        return resolve_path(data_dir, relative_path).is_file()
    except ValueError:
        return False


def delete_file(data_dir: Path, relative_path: str) -> None:
    """Remove a single image file and prune empty parent directories."""
    try:
        path = resolve_path(data_dir, relative_path)
    except ValueError:
        return
    if path.is_file():
        path.unlink()
    _prune_empty_dirs(path.parent, images_root(data_dir))


def delete_entry_dir(data_dir: Path, entry_date: date, entry_id: str) -> None:
    """Remove the entire image folder for an entry (cascade helper)."""
    dir_path = (
        images_root(data_dir)
        / f"{entry_date.year:04d}"
        / f"{entry_date.month:02d}"
        / entry_id
    )
    if dir_path.is_dir():
        shutil.rmtree(dir_path, ignore_errors=True)
    _prune_empty_dirs(dir_path.parent, images_root(data_dir))


def total_bytes_on_disk(data_dir: Path) -> int:
    """Sum file sizes under the images root (for stats / warnings)."""
    root = images_root(data_dir)
    if not root.is_dir():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def _prune_empty_dirs(start: Path, stop_at: Path) -> None:
    """Walk up from *start* removing empty directories until *stop_at*."""
    current = start
    stop = stop_at.resolve()
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
