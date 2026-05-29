"""Recursive file discovery with ignore filtering."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from togra.config import OUTPUT_DIR_NAME, SUPPORTED_EXTENSIONS
from togra.ignore import IgnoreMatcher


def collect_files(
    root: Path,
    ignore: IgnoreMatcher,
    *,
    extensions: Iterable[str] | None = None,
    include_unknown: bool = True,
) -> list[Path]:
    """Walk ``root`` and return matching files (absolute paths).

    Parameters
    ----------
    root:
        Project root.  Must exist.
    ignore:
        Compiled ``.tograignore`` matcher.
    extensions:
        If provided, restrict to files with these suffixes (lower-case,
        including the leading dot).  ``None`` means "all suffixes known to
        togra plus, optionally, everything else (handled by fallback)".
    include_unknown:
        If True, include files whose extension is not in
        :data:`SUPPORTED_EXTENSIONS` so the fallback parser can record them.

    The output directory ``togra-output/`` and dot-directories produced by
    common tooling are never returned — they would loop the parser back on
    its own artefacts.
    """
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    ext_filter: frozenset[str] | None
    if extensions is None:
        ext_filter = None
    else:
        ext_filter = frozenset(e.lower() for e in extensions)

    output_dir = (root / OUTPUT_DIR_NAME).resolve()

    result: list[Path] = []
    for entry in root.rglob("*"):
        # Skip our own output dir to avoid recursion.
        try:
            if entry.resolve().is_relative_to(output_dir):
                continue
        except OSError:
            # Broken symlink — ignore.
            continue

        if not entry.is_file():
            continue

        suffix = entry.suffix.lower()
        if ext_filter is not None:
            if suffix not in ext_filter:
                continue
        elif not include_unknown and suffix not in SUPPORTED_EXTENSIONS:
            continue

        try:
            rel = entry.relative_to(root).as_posix()
        except ValueError:
            continue

        if ignore.matches(rel, is_dir=False):
            continue

        result.append(entry)

    result.sort()
    return result
