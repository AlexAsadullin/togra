"""Merge cached and freshly-parsed fragments into the final graph dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from togra.cache import store as cache_store
from togra.graph.tree import insert_into_tree


def build_graph_tree(
    *,
    dirty_fragments: dict[str, dict[str, Any]],
    clean_paths: list[str],
    index: dict[str, dict[str, str]],
    output_dir: Path,
) -> dict[str, Any]:
    """Assemble the final graph dict.

    Parameters
    ----------
    dirty_fragments:
        ``{rel_path: fragment}`` for freshly-parsed files.  Their fragments
        are also saved to disk by the caller via :mod:`togra.cache.store`.
    clean_paths:
        Relative paths whose cached fragments should be loaded as-is.
    index:
        Cache index used to locate fragments for ``clean_paths``.
    """
    graph: dict[str, Any] = {
        "project_root": {"_meta": {"type": "directory", "path": "."}}
    }

    for rel_path, fragment in dirty_fragments.items():
        insert_into_tree(graph, rel_path, fragment)

    for rel_path in clean_paths:
        entry = index.get(rel_path)
        if entry is None:
            continue
        fragment_name = entry.get("fragment", "")
        if not fragment_name:
            continue
        fragment = cache_store.load_fragment(output_dir, fragment_name)
        if fragment is None:
            continue
        insert_into_tree(graph, rel_path, fragment)

    return graph
