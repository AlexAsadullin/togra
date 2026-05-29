"""Parser protocol used by the registry."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from togra.schema import FileNode


class Parser(Protocol):
    """A language-specific parser.

    Implementations must be pure: they receive the file's raw bytes plus the
    information needed for resolving relative imports, and return a
    :class:`FileNode`.  No I/O outside the provided content; no network
    calls of any kind.
    """

    lang: str

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:  # pragma: no cover - protocol
        ...
