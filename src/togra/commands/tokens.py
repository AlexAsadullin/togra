"""``togra tokens`` — approximate Claude-style token count for files or graph.

We deliberately stay offline (per project rules — no LLM clients, no
network calls).  The Anthropic / Claude tokeniser is not shipped, so we
use a transparent heuristic: ``tokens ≈ ceil(len(text) / CHARS_PER_TOKEN)``.

``CHARS_PER_TOKEN`` defaults to ``3.5``, a widely-cited average for mixed
code + English prose with the Claude tokeniser.  The number is documented
and exposed so users can recalibrate against their own corpora if they
care about exactness.
"""

from __future__ import annotations

import math
from pathlib import Path

from rich.console import Console
from rich.table import Table

from togra.config import (
    GRAPH_FILENAME,
    IGNORE_FILENAME,
    OUTPUT_DIR_NAME,
    SUPPORTED_EXTENSIONS,
)
from togra.fs.collect import collect_files
from togra.ignore import IgnoreMatcher
from togra.parsers.registry import lang_for_path

# Average chars per token for the Claude tokeniser on mixed code/prose.
# Empirical, not exact.  Override via the CLI if you have a better estimate.
CHARS_PER_TOKEN = 3.5


def count_tokens(text: str, *, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    """Approximate number of Claude tokens in ``text``.

    Uses a length-based heuristic — see module docstring for the rationale.
    Returns 0 for empty input, otherwise at least 1.
    """
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


def _load_ignore(project_root: Path) -> IgnoreMatcher:
    path = project_root / IGNORE_FILENAME
    if path.exists():
        return IgnoreMatcher.from_text(path.read_text(encoding="utf-8"))
    return IgnoreMatcher.empty()


def _safe_read_text(path: Path) -> str:
    """Read a file as UTF-8; on decode failure return the raw byte length."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fall back to a length-preserving lossy decode so the token estimate
        # still reflects file size for binary-ish inputs.
        return path.read_bytes().decode("utf-8", errors="replace")


def run_tokens(
    target: Path,
    *,
    project_root: Path,
    graph: bool = False,
    lang_filter: set[str] | None = None,
    output_dir: Path | None = None,
    chars_per_token: float = CHARS_PER_TOKEN,
    verbose: bool = False,
    console: Console | None = None,
) -> int:
    """Print a token-count report; return the total token count."""
    console = console or Console()

    # --- mode 1: count tokens in graph.json -------------------------------
    if graph:
        if output_dir is None:
            output_dir = project_root / OUTPUT_DIR_NAME
        graph_path = output_dir / GRAPH_FILENAME
        if not graph_path.exists():
            console.print(
                f"[red]error[/red]: {graph_path} not found. "
                "Run `togra build` first."
            )
            return 0
        text = _safe_read_text(graph_path)
        total = count_tokens(text, chars_per_token=chars_per_token)
        console.print(
            f"[bold]{graph_path}[/bold]: "
            f"[cyan]{len(text)}[/cyan] chars, "
            f"[green]~{total}[/green] tokens "
            f"(≈ {chars_per_token} chars/token)"
        )
        return total

    # --- mode 2: count tokens in a single file ----------------------------
    if target.is_file():
        text = _safe_read_text(target)
        total = count_tokens(text, chars_per_token=chars_per_token)
        rel = _try_relative(target, project_root)
        console.print(
            f"[bold]{rel}[/bold]: "
            f"[cyan]{len(text)}[/cyan] chars, "
            f"[green]~{total}[/green] tokens"
        )
        return total

    # --- mode 3: walk a directory ----------------------------------------
    if not target.exists():
        console.print(f"[red]error[/red]: {target} not found")
        return 0
    if not target.is_dir():
        console.print(f"[red]error[/red]: {target} is neither a file nor a directory")
        return 0

    ignore = _load_ignore(project_root)
    files = collect_files(target, ignore, extensions=SUPPORTED_EXTENSIONS)
    if lang_filter:
        files = [f for f in files if lang_for_path(f.as_posix()) in lang_filter]

    per_file: list[tuple[str, str, int, int]] = []  # (rel, lang, chars, tokens)
    totals_by_lang: dict[str, tuple[int, int, int]] = {}  # lang -> (files, chars, tokens)
    grand_chars = 0
    grand_tokens = 0

    for f in files:
        text = _safe_read_text(f)
        chars = len(text)
        toks = count_tokens(text, chars_per_token=chars_per_token)
        lang = lang_for_path(f.as_posix())
        rel = _try_relative(f, project_root)
        per_file.append((rel, lang, chars, toks))
        prev_files, prev_chars, prev_toks = totals_by_lang.get(lang, (0, 0, 0))
        totals_by_lang[lang] = (prev_files + 1, prev_chars + chars, prev_toks + toks)
        grand_chars += chars
        grand_tokens += toks

    if verbose and per_file:
        per_file.sort(key=lambda row: row[3], reverse=True)
        ft = Table(title="tokens by file")
        ft.add_column("file", overflow="fold")
        ft.add_column("lang")
        ft.add_column("chars", justify="right")
        ft.add_column("~tokens", justify="right")
        for rel, lang, chars, toks in per_file:
            ft.add_row(rel, lang, str(chars), str(toks))
        console.print(ft)

    if totals_by_lang:
        lt = Table(title="tokens by language")
        lt.add_column("lang")
        lt.add_column("files", justify="right")
        lt.add_column("chars", justify="right")
        lt.add_column("~tokens", justify="right")
        for lang in sorted(totals_by_lang):
            n_files, n_chars, n_toks = totals_by_lang[lang]
            lt.add_row(lang, str(n_files), str(n_chars), str(n_toks))
        console.print(lt)

    console.print(
        f"\n[bold]total[/bold]: "
        f"[cyan]{len(files)}[/cyan] files, "
        f"[cyan]{grand_chars}[/cyan] chars, "
        f"[green]~{grand_tokens}[/green] tokens "
        f"(heuristic: {chars_per_token} chars/token)"
    )
    return grand_tokens


def _try_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
