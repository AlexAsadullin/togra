"""On-disk cache: ``index.json`` + per-file fragments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from togra.config import (
    CACHE_DIRNAME,
    CACHE_INDEX_FILENAME,
    FRAGMENTS_DIRNAME,
)
from togra.fs.atomic import atomic_write_json


def cache_dir(output_dir: Path) -> Path:
    return output_dir / CACHE_DIRNAME


def fragments_dir(output_dir: Path) -> Path:
    return cache_dir(output_dir) / FRAGMENTS_DIRNAME


def index_path(output_dir: Path) -> Path:
    return cache_dir(output_dir) / CACHE_INDEX_FILENAME


def load_index(output_dir: Path) -> dict[str, dict[str, str]]:
    """Load ``index.json`` or return an empty dict."""
    p = index_path(output_dir)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupt index — treat as empty, downstream will rebuild.
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def save_index(output_dir: Path, index: dict[str, dict[str, str]]) -> None:
    atomic_write_json(index_path(output_dir), index)


def fragment_path(output_dir: Path, fragment_name: str) -> Path:
    return fragments_dir(output_dir) / fragment_name


def fragment_name_for(file_hash: str) -> str:
    """The cache file storing the fragment for a given content hash."""
    return f"{file_hash}.json"


def save_fragment(output_dir: Path, file_hash: str, fragment: dict[str, Any]) -> str:
    """Persist ``fragment`` and return the basename written into the index."""
    name = fragment_name_for(file_hash)
    atomic_write_json(fragment_path(output_dir, name), fragment)
    return name


def load_fragment(output_dir: Path, fragment_name: str) -> dict[str, Any] | None:
    p = fragment_path(output_dir, fragment_name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def delete_fragment(output_dir: Path, fragment_name: str) -> None:
    p = fragment_path(output_dir, fragment_name)
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def ensure_cache_layout(output_dir: Path) -> None:
    """Create ``cache/`` and ``cache/fragments/`` (idempotent)."""
    fragments_dir(output_dir).mkdir(parents=True, exist_ok=True)
    idx = index_path(output_dir)
    if not idx.exists():
        atomic_write_json(idx, {})
