"""``togra info`` — print statistics about the current build."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from togra.cache import store as cache_store
from togra.config import GRAPH_FILENAME, MANIFEST_FILENAME, OUTPUT_DIR_NAME


def run_info(
    project_root: Path,
    *,
    output_dir: Path | None = None,
    verbose: bool = False,
    console: Console | None = None,
) -> None:
    console = console or Console()
    if output_dir is None:
        output_dir = project_root / OUTPUT_DIR_NAME
    if not output_dir.exists():
        console.print(
            f"[red]error[/red]: {output_dir} not found. Run `togra init` first."
        )
        return

    manifest_path = output_dir / MANIFEST_FILENAME
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    index = cache_store.load_index(output_dir)
    graph_path = output_dir / GRAPH_FILENAME
    graph_size = graph_path.stat().st_size if graph_path.exists() else 0

    table = Table(title="togra status", show_header=False, box=None)
    table.add_row("output dir", str(output_dir))
    table.add_row("graph.json", f"{graph_size} bytes" if graph_size else "(missing)")
    table.add_row("cached fragments", str(len(index)))
    table.add_row("togra version", str(manifest.get("version", "?")))
    table.add_row("last build", str(manifest.get("last_build", "—")))

    stats = manifest.get("stats", {}) or {}
    if stats:
        for key in ("files_total", "dirty", "clean", "removed", "mode"):
            if key in stats:
                table.add_row(key, str(stats[key]))
        by_lang = stats.get("by_lang") or {}
        if by_lang:
            table.add_row(
                "last_build by lang",
                ", ".join(f"{k}={v}" for k, v in sorted(by_lang.items())),
            )

    console.print(table)

    if verbose:
        # Per-lang count of cached fragments.
        lang_counts: dict[str, int] = {}
        for entry in index.values():
            lang = entry.get("lang", "?")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts:
            console.print(
                "\n[bold]Cache by language[/bold]: "
                + ", ".join(f"{k}={v}" for k, v in sorted(lang_counts.items()))
            )
