"""SHA256 file hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 8192


def compute_file_hash(path: Path) -> str:
    """Return the SHA256 hex digest of ``path``'s contents.

    Reads the file in 8 KiB chunks so we don't load large files in memory.
    Raises :class:`FileNotFoundError` if the path does not exist and
    :class:`PermissionError` if it is unreadable — callers must decide how
    to handle those.
    """
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_bytes(data: bytes) -> str:
    """SHA256 of an in-memory blob — used by tests and the Vue helper."""
    return hashlib.sha256(data).hexdigest()
