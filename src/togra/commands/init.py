"""``togra init`` — bootstrap ``togra-output/`` and ``.tograignore``."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from rich.console import Console

from togra import __version__
from togra.cache.store import ensure_cache_layout
from togra.config import (
    AGENT_GUIDE_FILENAME,
    DEFAULT_TOGRAIGNORE,
    IGNORE_FILENAME,
    MANIFEST_FILENAME,
    OUTPUT_DIR_NAME,
)
from togra.fs.atomic import atomic_write_json


def _read_bundled_agent_guide() -> str:
    """Return the ``AGENT_GUIDE.md`` text shipped inside the package."""
    return (
        resources.files("togra.templates")
        .joinpath(AGENT_GUIDE_FILENAME)
        .read_text(encoding="utf-8")
    )


def run_init(project_root: Path, *, console: Console | None = None) -> Path:
    """Create the output directory layout and ``.tograignore``.

    Returns the path to ``togra-output/`` for downstream commands.
    """
    console = console or Console()

    output_dir = project_root / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_cache_layout(output_dir)

    # `.tograignore`
    ignore_path = project_root / IGNORE_FILENAME
    if not ignore_path.exists():
        gitignore = project_root / ".gitignore"
        if gitignore.exists():
            ignore_path.write_text(
                gitignore.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            console.print(f"[green]copied[/green] .gitignore → {IGNORE_FILENAME}")
        else:
            ignore_path.write_text(DEFAULT_TOGRAIGNORE, encoding="utf-8")
            console.print(
                f"[yellow]warning[/yellow]: no .gitignore found, "
                f"wrote default {IGNORE_FILENAME}"
            )
    else:
        console.print(f"[dim]{IGNORE_FILENAME} already exists, leaving as-is[/dim]")

    # AGENT_GUIDE.md
    guide_path = project_root / AGENT_GUIDE_FILENAME
    if not guide_path.exists():
        guide_path.write_text(_read_bundled_agent_guide(), encoding="utf-8")
        console.print(f"[green]created[/green] {AGENT_GUIDE_FILENAME}")
    else:
        console.print(f"[dim]{AGENT_GUIDE_FILENAME} already exists, leaving as-is[/dim]")

    # manifest.json
    manifest_path = output_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        atomic_write_json(
            manifest_path,
            {
                "version": __version__,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "project_root": str(project_root.resolve()),
                "last_build": None,
                "stats": {},
            },
        )

    # Friendly nudge about .git presence — not an error.
    if not (project_root / ".git").exists():
        console.print(
            "[yellow]note[/yellow]: no .git directory found; "
            "togra works without git but graph history won't be tracked."
        )

    console.print(f"[bold green]✓[/bold green] initialised {output_dir}")
    return output_dir
