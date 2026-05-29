"""Typer CLI: ``togra init|build|info|clean``."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from togra import __version__
from togra.commands.build import run_build
from togra.commands.clean import run_clean
from togra.commands.info import run_info
from togra.commands.init import run_init
from togra.commands.tokens import CHARS_PER_TOKEN, run_tokens

app = typer.Typer(
    name="togra",
    help="Token-Graph: offline algorithmic project-graph builder. "
    "Generates togra-output/graph.json with empty `description` fields "
    "for downstream AI agents.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"togra {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", help="Print version and exit.", is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """togra — offline project-graph builder."""


def _project_root(root: Path | None) -> Path:
    return (root or Path.cwd()).resolve()


@app.command("init")
def cmd_init(
    project: Path = typer.Option(
        Path("."), "--project", "-p", help="Project root (default: cwd)."
    ),
) -> None:
    """Bootstrap togra-output/ and .tograignore in the project."""
    run_init(_project_root(project), console=console)


@app.command("build")
def cmd_build(
    project: Path = typer.Option(
        Path("."), "--project", "-p", help="Project root (default: cwd)."
    ),
    update: bool = typer.Option(
        False, "--update", "-u", help="Incremental update (default behaviour)."
    ),
    full: bool = typer.Option(
        False, "--full", "-f", help="Rebuild the graph from scratch."
    ),
    newonly: bool = typer.Option(
        False, "--newonly", "-n", help="Only parse files absent from the cache."
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Custom path for graph.json."
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-d", help="Custom togra-output/ location."
    ),
    lang: Optional[str] = typer.Option(
        None, "--lang", "-l",
        help="Comma-separated language filter (e.g. python,typescript).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
) -> None:
    """Build togra-output/graph.json."""
    mode_flags = sum([full, newonly])
    if mode_flags > 1:
        typer.echo("Choose at most one of --full / --newonly.", err=True)
        raise typer.Exit(code=2)
    if full:
        mode = "full"
    elif newonly:
        mode = "newonly"
    else:
        # --update is the default whether or not the flag was passed.
        mode = "update"
        _ = update  # silence unused

    lang_filter: set[str] | None = None
    if lang:
        lang_filter = {item.strip().lower() for item in lang.split(",") if item.strip()}

    run_build(
        _project_root(project),
        mode=mode,
        lang_filter=lang_filter,
        output_dir=output_dir.resolve() if output_dir else None,
        output_file=output.resolve() if output else None,
        verbose=verbose,
        console=console,
    )


@app.command("info")
def cmd_info(
    project: Path = typer.Option(Path("."), "--project", "-p"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-d"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Show cache + last build statistics."""
    run_info(
        _project_root(project),
        output_dir=output_dir.resolve() if output_dir else None,
        verbose=verbose,
        console=console,
    )


@app.command("clean")
def cmd_clean(
    project: Path = typer.Option(Path("."), "--project", "-p"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-d"),
    all_: bool = typer.Option(
        False, "--all", help="Remove the entire togra-output/ directory."
    ),
) -> None:
    """Drop cached fragments (or the whole output dir with --all)."""
    run_clean(
        _project_root(project),
        output_dir=output_dir.resolve() if output_dir else None,
        all_=all_,
        console=console,
    )


@app.command("tokens")
def cmd_tokens(
    path: Path = typer.Argument(
        Path("."),
        help="File or directory to scan (default: project root).",
    ),
    project: Path = typer.Option(
        Path("."), "--project", "-p", help="Project root (default: cwd)."
    ),
    graph: bool = typer.Option(
        False, "--graph", "-g",
        help="Count tokens in togra-output/graph.json instead of source.",
    ),
    lang: Optional[str] = typer.Option(
        None, "--lang", "-l",
        help="Comma-separated language filter (e.g. python,typescript).",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-d",
        help="Custom togra-output/ location (used with --graph).",
    ),
    chars_per_token: float = typer.Option(
        CHARS_PER_TOKEN, "--chars-per-token",
        help="Heuristic ratio. Lower = more tokens per char.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Per-file breakdown."
    ),
) -> None:
    """Approximate Claude-style token count for files / graph.

    Uses an offline heuristic (default ~3.5 chars per token). No LLM calls,
    no network — counts work even with the project disconnected.
    """
    root = _project_root(project)
    lang_filter: set[str] | None = None
    if lang:
        lang_filter = {item.strip().lower() for item in lang.split(",") if item.strip()}
    run_tokens(
        path.resolve() if path.is_absolute() else (root / path).resolve(),
        project_root=root,
        graph=graph,
        lang_filter=lang_filter,
        output_dir=output_dir.resolve() if output_dir else None,
        chars_per_token=chars_per_token,
        verbose=verbose,
        console=console,
    )


if __name__ == "__main__":
    app()
