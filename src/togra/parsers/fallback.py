"""Fallback parser used when no language-specific parser applies.

Per user instruction: for any unsupported language, emit a minimal node
that records the relative path and lang ``"unknown"``, with an empty
``description`` and no classes/functions/imports.
"""

from __future__ import annotations

from pathlib import Path

from togra.config import EXTENSION_TO_LANG
from togra.schema import FileMeta, FileNode


class FallbackParser:
    lang = "unknown"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        suffix = Path(rel_path).suffix.lower()
        lang = EXTENSION_TO_LANG.get(suffix, "unknown")
        meta = FileMeta(lang=lang, hash=file_hash, path=rel_path)
        return FileNode(_meta=meta)
