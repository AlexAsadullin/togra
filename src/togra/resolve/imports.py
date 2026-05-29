"""Import path & type resolution helpers."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

# Extensions to probe when resolving an internal import.
_PROBE_EXTENSIONS = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue")


def resolve_import_type(name: str) -> str:
    """Heuristic classification of an imported symbol.

    * ``UPPER_CASE`` → ``"constant"``
    * ``CamelCase`` → ``"class"``
    * everything else → ``"function"`` (fallback covering plain functions
      and variables; downstream consumers can refine).

    Per tech-task §6.4.  No file I/O.
    """
    if not name:
        return "unknown"
    if name.isupper():
        return "constant"
    first = name[0]
    if first.isupper() and "_" not in name:
        return "class"
    return "function"


def resolve_relative_path(
    import_module: str,
    current_file: Path,
    project_root: Path,
) -> str:
    """Translate a Python-style dotted import into a path relative to root.

    Handles leading ``.`` / ``..`` for relative imports.  Probes for a file
    with one of :data:`_PROBE_EXTENSIONS` and also for a ``__init__.py``
    package marker.  Returns the project-relative POSIX path on success,
    otherwise the original ``import_module`` unchanged so the caller can
    still record the symbol.
    """
    if not import_module:
        return import_module

    # Count leading dots.
    leading_dots = 0
    for ch in import_module:
        if ch == ".":
            leading_dots += 1
        else:
            break
    remainder = import_module[leading_dots:]
    parts = [p for p in remainder.split(".") if p]

    try:
        if leading_dots == 0:
            base = project_root
        else:
            # 1 dot = current dir, 2 dots = parent, ...
            base = current_file.parent
            for _ in range(leading_dots - 1):
                base = base.parent
    except IndexError:
        return import_module

    target = base.joinpath(*parts) if parts else base

    for ext in _PROBE_EXTENSIONS:
        candidate = target.with_suffix(ext) if parts else None
        if candidate is not None and candidate.exists():
            return _safe_relative(candidate, project_root)

    init_candidate = target / "__init__.py"
    if init_candidate.exists():
        return _safe_relative(init_candidate, project_root)

    if target.exists() and target.is_dir():
        return _safe_relative(target, project_root)

    return import_module


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()
    except ValueError:
        return path.as_posix()
