"""Atomic JSON writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write ``data`` as JSON to ``path`` atomically.

    Strategy: write to a sibling ``.tmp`` file in the same directory and
    ``os.replace`` it onto the target.  ``os.replace`` is atomic on POSIX
    and Windows when both paths live on the same filesystem.

    The parent directory is created if missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile in the same directory guarantees same-FS rename.
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, sort_keys=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; ignore if already gone.
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise
