"""Simplified CSS parser.

Per tech-task §4: for CSS we record selectors, ``@import`` rules and
``url(...)`` references — no AST, no class/function extraction.
"""

from __future__ import annotations

import re
from pathlib import Path

from togra.schema import FileMeta, FileNode

_COMMENT_RE = re.compile(rb"/\*.*?\*/", re.DOTALL)
_IMPORT_RE = re.compile(
    rb"@import\s+(?:url\(\s*)?['\"]?([^'\")\s;]+)",
    re.IGNORECASE,
)
_URL_RE = re.compile(rb"url\(\s*['\"]?([^'\")\s]+)", re.IGNORECASE)
# A selector body cannot contain ``{``, ``}`` or ``;``.  We also exclude an
# explicit ``@`` to avoid swallowing at-rules; @-rule selectors themselves
# are captured separately by :data:`_AT_MEDIA_RE`.
_SELECTOR_RE = re.compile(rb"([^{};@][^{};]*?)\s*\{")
_AT_MEDIA_RE = re.compile(rb"@media[^{]+", re.IGNORECASE)
_SINGLE_LINE_AT_RULE_RE = re.compile(rb"@[a-zA-Z-]+[^;{}]*;")


class CssParser:
    lang = "css"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        del project_root  # unused
        stripped = _COMMENT_RE.sub(b"", content)
        # Drop single-line at-rules like `@import ...;` so the selector
        # regex doesn't trip over them.
        selector_source = _SINGLE_LINE_AT_RULE_RE.sub(b"", stripped)

        selectors: list[str] = []
        seen_sel: set[str] = set()
        for match in _SELECTOR_RE.finditer(selector_source):
            sel = match.group(1).decode("utf-8", errors="replace").strip()
            if not sel or sel.startswith("@"):
                continue
            # Split combined selectors `a, b, c` and drop duplicates.
            for piece in (p.strip() for p in sel.split(",")):
                if piece and piece not in seen_sel:
                    seen_sel.add(piece)
                    selectors.append(piece)

        media_queries = [
            m.group(0).decode("utf-8", errors="replace").strip()
            for m in _AT_MEDIA_RE.finditer(stripped)
        ]

        imports = [
            m.group(1).decode("utf-8", errors="replace")
            for m in _IMPORT_RE.finditer(stripped)
        ]
        urls = [
            m.group(1).decode("utf-8", errors="replace")
            for m in _URL_RE.finditer(stripped)
        ]

        meta = FileMeta(lang="css", hash=file_hash, path=rel_path)
        file_node = FileNode(_meta=meta)
        file_node.extras["selectors"] = selectors
        if media_queries:
            file_node.extras["media_queries"] = media_queries
        if imports:
            file_node.extras["imports_css"] = imports
        if urls:
            file_node.extras["urls"] = urls
        return file_node
