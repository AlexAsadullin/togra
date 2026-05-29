"""Insertion of file fragments into the nested project tree."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def insert_into_tree(graph: dict[str, Any], rel_path: str, fragment: dict[str, Any]) -> None:
    """Insert ``fragment`` at ``rel_path`` inside ``graph["project_root"]``.

    Intermediate directories are created on demand with a ``_meta`` stub.
    The leaf is stored under its filename key.
    """
    if "project_root" not in graph:
        graph["project_root"] = {"_meta": {"type": "directory", "path": "."}}

    parts = list(PurePosixPath(rel_path).parts)
    if not parts:
        return

    current = graph["project_root"]
    current_path_parts: list[str] = []
    for part in parts[:-1]:
        current_path_parts.append(part)
        if part not in current:
            current[part] = {
                "_meta": {
                    "type": "directory",
                    "path": "/".join(current_path_parts),
                }
            }
        else:
            # Ensure the existing entry is a directory node, not a file
            # shadowed by an earlier insert.
            child = current[part]
            if not isinstance(child, dict) or child.get("_meta", {}).get("type") != "directory":
                current[part] = {
                    "_meta": {
                        "type": "directory",
                        "path": "/".join(current_path_parts),
                    }
                }
        current = current[part]

    current[parts[-1]] = fragment
