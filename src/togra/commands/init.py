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
    CLAUDE_DIR_NAME,
    CLAUDE_INSTRUCTIONS_FILENAME,
    CLAUDE_INSTRUCTIONS_TEMPLATE,
    DEFAULT_TOGRAIGNORE,
    IGNORE_FILENAME,
    MANIFEST_FILENAME,
    OUTPUT_DIR_NAME,
)
from togra.fs.atomic import atomic_write_json


def _read_template(name: str) -> str:
    """Return text of a bundled template under ``togra.templates``."""
    return resources.files("togra.templates").joinpath(name).read_text(encoding="utf-8")


def _read_bundled_agent_guide() -> str:
    return _read_template(AGENT_GUIDE_FILENAME)


def run_init(
    project_root: Path,
    *,
    console: Console | None = None,
    claude: bool = False,
) -> Path:
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

    # AGENT_GUIDE.md — lives inside togra-output/ so it ships with the
    # graph for the downstream AI agent and stays out of the project root.
    guide_path = output_dir / AGENT_GUIDE_FILENAME
    if not guide_path.exists():
        guide_path.write_text(_read_bundled_agent_guide(), encoding="utf-8")
        console.print(f"[green]created[/green] {guide_path.relative_to(project_root)}")
    else:
        console.print(
            f"[dim]{guide_path.relative_to(project_root)} already exists, "
            "leaving as-is[/dim]"
        )

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

    # Optional Claude Code instructions.
    if claude:
        claude_dir = project_root / CLAUDE_DIR_NAME
        claude_dir.mkdir(parents=True, exist_ok=True)
        instructions_path = claude_dir / CLAUDE_INSTRUCTIONS_FILENAME
        rel = instructions_path.relative_to(project_root)
        if not instructions_path.exists():
            instructions_path.write_text(
                _read_template(CLAUDE_INSTRUCTIONS_TEMPLATE), encoding="utf-8"
            )
            console.print(f"[green]created[/green] {rel}")
        else:
            console.print(f"[dim]{rel} already exists, leaving as-is[/dim]")

    # Friendly nudge about .git presence — not an error.
    if not (project_root / ".git").exists():
        console.print(
            "[yellow]note[/yellow]: no .git directory found; "
            "togra works without git but graph history won't be tracked."
        )

    console.print(f"[bold green]✓[/bold green] initialised {output_dir}")
    return output_dir
