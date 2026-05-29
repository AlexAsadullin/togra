"""SHA256-based dirty-file detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from togra.fs.hashing import compute_file_hash


@dataclass
class DiffResult:
    """Outcome of comparing the working tree against the cache index."""

    #: Files that need (re)parsing.  Maps relative POSIX path → new hash.
    dirty: dict[str, str] = field(default_factory=dict)
    #: Files present in both tree and cache with matching hashes.  Same
    #: shape as ``dirty``.
    clean: dict[str, str] = field(default_factory=dict)
    #: Entries that exist only in the index (file was deleted on disk).
    removed: list[str] = field(default_factory=list)
    #: Files seen on disk that are not yet indexed.
    new: list[str] = field(default_factory=list)


def diff_files(
    files: list[Path],
    root: Path,
    index: dict[str, dict[str, str]],
    *,
    mode: str = "update",
) -> DiffResult:
    """Compute a :class:`DiffResult` for the given working tree snapshot.

    ``mode`` controls which files end up in ``dirty``:

    * ``"update"`` — every changed or new file is dirty (default behaviour
      of ``togra build``).
    * ``"full"`` — every collected file is dirty; the cache is ignored
      for decision-making but ``removed`` still lists vanished entries.
    * ``"newonly"`` — only files absent from the index are dirty; modified
      ones are kept as clean (caller will load their cached fragment).
    """
    if mode not in {"update", "full", "newonly"}:
        raise ValueError(f"unknown diff mode: {mode!r}")

    result = DiffResult()
    seen: set[str] = set()

    for file in files:
        rel = file.relative_to(root).as_posix()
        seen.add(rel)
        new_hash = compute_file_hash(file)
        cached = index.get(rel)

        if mode == "full":
            result.dirty[rel] = new_hash
            if cached is None:
                result.new.append(rel)
            continue

        if cached is None:
            result.new.append(rel)
            result.dirty[rel] = new_hash
            continue

        if cached.get("hash") == new_hash:
            result.clean[rel] = new_hash
        else:
            if mode == "newonly":
                # Keep the cached fragment; do not re-parse.
                result.clean[rel] = cached.get("hash", new_hash)
            else:
                result.dirty[rel] = new_hash

    for rel in index.keys() - seen:
        result.removed.append(rel)

    return result
