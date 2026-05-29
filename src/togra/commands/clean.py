"""``togra clean`` — remove cache (or the entire ``togra-output/``)."""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from togra.cache import store as cache_store
from togra.config import OUTPUT_DIR_NAME


def run_clean(
    project_root: Path,
    *,
    output_dir: Path | None = None,
    all_: bool = False,
    console: Console | None = None,
) -> None:
    console = console or Console()
    if output_dir is None:
        output_dir = project_root / OUTPUT_DIR_NAME

    if not output_dir.exists():
        console.print(f"[dim]{output_dir} does not exist, nothing to clean[/dim]")
        return

    if all_:
        shutil.rmtree(output_dir)
        console.print(f"[bold red]✗[/bold red] removed {output_dir}")
        return

    cache_dir = cache_store.cache_dir(output_dir)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_store.ensure_cache_layout(output_dir)
    console.print(f"[bold green]✓[/bold green] cache cleared in {output_dir}")
