"""Ensure togra does not import any network-capable client."""

from __future__ import annotations

import ast
from pathlib import Path

import togra

FORBIDDEN_TOP_LEVEL = {
    "openai", "anthropic", "requests", "httpx", "urllib3",
    "aiohttp", "boto3", "google", "langchain", "llama_index",
    "networkx", "graspologic",
}


def _iter_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def test_no_forbidden_imports():
    pkg_root = Path(togra.__file__).resolve().parent
    offenders: list[tuple[str, str]] = []
    for py_file in pkg_root.rglob("*.py"):
        for name in _iter_imports(py_file):
            if name in FORBIDDEN_TOP_LEVEL:
                offenders.append((str(py_file), name))
    assert not offenders, f"forbidden imports: {offenders}"


def test_urllib_request_not_used():
    pkg_root = Path(togra.__file__).resolve().parent
    for py_file in pkg_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "urllib.request" not in text, f"{py_file} uses urllib.request"
