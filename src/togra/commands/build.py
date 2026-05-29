"""``togra build`` — full pipeline (collect → hash → diff → parse → merge → write)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from togra import __version__
from togra.cache import store as cache_store
from togra.cache.diff import diff_files
from togra.commands.init import run_init
from togra.config import (
    GRAPH_FILENAME,
    IGNORE_FILENAME,
    MANIFEST_FILENAME,
    OUTPUT_DIR_NAME,
    SUPPORTED_EXTENSIONS,
)
from togra.fs.atomic import atomic_write_json
from togra.fs.collect import collect_files
from togra.graph.builder import build_graph_tree
from togra.ignore import IgnoreMatcher
from togra.parsers.registry import lang_for_path, parser_for_lang
from togra.schema import assert_descriptions_empty


def _load_ignore(project_root: Path) -> IgnoreMatcher:
    path = project_root / IGNORE_FILENAME
    if path.exists():
        return IgnoreMatcher.from_text(path.read_text(encoding="utf-8"))
    return IgnoreMatcher.empty()


def _filter_by_lang(files, lang_filter: set[str] | None):
    if not lang_filter:
        return files
    out = []
    for f in files:
        lang = lang_for_path(f.as_posix())
        if lang in lang_filter:
            out.append(f)
    return out


def _parse_one(
    *,
    project_root: Path,
    rel_path: str,
    new_hash: str,
) -> tuple[str, dict[str, Any], str]:
    """Read + parse a single file.  Returns (rel_path, fragment_dict, lang)."""
    abs_path = project_root / rel_path
    content = abs_path.read_bytes()
    lang = lang_for_path(rel_path)
    parser = parser_for_lang(lang)
    node = parser.parse(
        content=content,
        rel_path=rel_path,
        project_root=project_root,
        file_hash=new_hash,
    )
    # Stamp last_updated in UTC.
    node.meta.last_updated = datetime.now(timezone.utc).isoformat()
    return rel_path, node.to_fragment(), lang


def run_build(
    project_root: Path,
    *,
    mode: str = "update",
    lang_filter: set[str] | None = None,
    output_dir: Path | None = None,
    output_file: Path | None = None,
    verbose: bool = False,
    console: Console | None = None,
    max_workers: int | None = None,
) -> Path:
    """Execute the build pipeline.

    Returns the path to ``graph.json``.
    """
    console = console or Console()

    if output_dir is None:
        output_dir = project_root / OUTPUT_DIR_NAME
    if not output_dir.exists():
        if verbose:
            console.print(f"[dim]bootstrapping {output_dir} via init[/dim]")
        run_init(project_root, console=console)
    cache_store.ensure_cache_layout(output_dir)

    if output_file is None:
        output_file = output_dir / GRAPH_FILENAME

    ignore = _load_ignore(project_root)

    if verbose:
        console.print("[bold]→[/bold] collecting files…")
    files = collect_files(project_root, ignore, extensions=SUPPORTED_EXTENSIONS)
    files = _filter_by_lang(files, lang_filter)
    if verbose:
        console.print(f"  found [cyan]{len(files)}[/cyan] candidate files")

    # `--full` clears the index up front so all files are dirty and the
    # removed list collapses to "files not present anywhere".
    if mode == "full":
        index: dict[str, dict[str, str]] = {}
    else:
        index = cache_store.load_index(output_dir)

    diff = diff_files(files, project_root, index, mode=mode)
    if verbose:
        console.print(
            f"  diff: [green]{len(diff.dirty)}[/green] dirty, "
            f"[blue]{len(diff.clean)}[/blue] clean, "
            f"[yellow]{len(diff.new)}[/yellow] new, "
            f"[red]{len(diff.removed)}[/red] removed"
        )

    new_index: dict[str, dict[str, str]] = {}
    # Carry forward clean entries (their hash matches the disk).
    for rel_path in diff.clean:
        entry = index.get(rel_path)
        if entry is not None:
            new_index[rel_path] = dict(entry)

    # Parse dirty files (possibly in parallel).
    dirty_fragments: dict[str, dict[str, Any]] = {}
    stats_by_lang: dict[str, int] = {}

    def submit_tasks():
        return [
            (rel_path, new_hash)
            for rel_path, new_hash in diff.dirty.items()
        ]

    tasks = submit_tasks()
    if tasks:
        if verbose:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            )
            progress.start()
            task_id = progress.add_task("parsing", total=len(tasks))
        else:
            progress = None
            task_id = None

        try:
            workers = max_workers if max_workers is not None else min(8, max(1, len(tasks)))
            if workers <= 1:
                results_iter = (
                    _parse_one(project_root=project_root, rel_path=rp, new_hash=h)
                    for rp, h in tasks
                )
                for rel_path, fragment, lang in results_iter:
                    _record_result(
                        rel_path, fragment, lang,
                        dirty_fragments, new_index, output_dir,
                        diff.dirty, stats_by_lang,
                    )
                    if progress is not None and task_id is not None:
                        progress.advance(task_id)
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [
                        pool.submit(
                            _parse_one,
                            project_root=project_root,
                            rel_path=rp,
                            new_hash=h,
                        )
                        for rp, h in tasks
                    ]
                    for fut in as_completed(futures):
                        rel_path, fragment, lang = fut.result()
                        _record_result(
                            rel_path, fragment, lang,
                            dirty_fragments, new_index, output_dir,
                            diff.dirty, stats_by_lang,
                        )
                        if progress is not None and task_id is not None:
                            progress.advance(task_id)
        finally:
            if progress is not None:
                progress.stop()

    # Drop fragments for files that have disappeared.
    for rel_path in diff.removed:
        entry = index.get(rel_path)
        if entry and entry.get("fragment"):
            cache_store.delete_fragment(output_dir, entry["fragment"])

    # Merge into graph.
    graph = build_graph_tree(
        dirty_fragments=dirty_fragments,
        clean_paths=list(diff.clean.keys()),
        index=new_index,
        output_dir=output_dir,
    )

    # Safety net: no description should ever be non-empty.
    assert_descriptions_empty(graph)

    # Persist outputs.
    cache_store.save_index(output_dir, new_index)
    atomic_write_json(output_file, graph)

    _update_manifest(
        output_dir,
        files_total=len(files),
        dirty=len(diff.dirty),
        clean=len(diff.clean),
        removed=len(diff.removed),
        by_lang=stats_by_lang,
        mode=mode,
    )

    if verbose:
        console.print(f"[bold green]✓[/bold green] wrote {output_file}")
    return output_file


def _record_result(
    rel_path: str,
    fragment: dict[str, Any],
    lang: str,
    dirty_fragments: dict[str, dict[str, Any]],
    new_index: dict[str, dict[str, str]],
    output_dir: Path,
    dirty_hashes: dict[str, str],
    stats_by_lang: dict[str, int],
) -> None:
    file_hash = dirty_hashes[rel_path]
    fragment_name = cache_store.save_fragment(output_dir, file_hash, fragment)
    dirty_fragments[rel_path] = fragment
    new_index[rel_path] = {
        "hash": file_hash,
        "lang": lang,
        "fragment": fragment_name,
    }
    stats_by_lang[lang] = stats_by_lang.get(lang, 0) + 1


def _update_manifest(
    output_dir: Path,
    *,
    files_total: int,
    dirty: int,
    clean: int,
    removed: int,
    by_lang: dict[str, int],
    mode: str,
) -> None:
    manifest_path = output_dir / MANIFEST_FILENAME
    existing: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            import json
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing["version"] = __version__
    existing["last_build"] = datetime.now(timezone.utc).isoformat()
    existing["stats"] = {
        "files_total": files_total,
        "dirty": dirty,
        "clean": clean,
        "removed": removed,
        "by_lang": by_lang,
        "mode": mode,
    }
    atomic_write_json(manifest_path, existing)
