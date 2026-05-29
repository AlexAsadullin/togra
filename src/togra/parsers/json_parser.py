"""Simplified JSON parser: emits a ``keys_tree`` summary, no AST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from togra.schema import FileMeta, FileNode


def _keys_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _keys_tree(v) for key, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        # Summarise heterogeneous arrays as a single-element shape descriptor.
        first = _keys_tree(value[0])
        return [first]
    return type(value).__name__


class JsonParser:
    lang = "json"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        del project_root
        meta = FileMeta(lang="json", hash=file_hash, path=rel_path)
        node = FileNode(_meta=meta)
        try:
            data = json.loads(content.decode("utf-8", errors="replace") or "null")
            node.extras["keys_tree"] = _keys_tree(data)
        except json.JSONDecodeError as exc:
            node.extras["keys_tree"] = None
            node.extras["parse_error"] = f"{exc.msg} (line {exc.lineno})"
        return node
