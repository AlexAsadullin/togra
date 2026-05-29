"""Vue Single-File Component parser.

Vue files are split into ``<template>``, ``<script>`` and ``<style>`` blocks.
We:

* delegate the ``<script>`` / ``<script setup>`` block to the JS/TS parser
  (per tech-task §4 — Vue maps to JS/TS rules);
* record component tags used inside ``<template>`` under
  ``extras.components_used`` (PascalCase or kebab-case identifiers).

The split is done with a lightweight regex rather than a dedicated Vue
grammar to stay within the allowed dependency set.
"""

from __future__ import annotations

import re
from pathlib import Path

from togra.parsers.js_ts_parser import parse_js_like
from togra.schema import FileMeta, FileNode


_SCRIPT_RE = re.compile(
    rb"<script\b([^>]*)>(.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_TEMPLATE_RE = re.compile(
    rb"<template\b[^>]*>(.*?)</template\s*>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(rb"<([A-Za-z][A-Za-z0-9_-]*)\b")


def _is_typescript(attrs: bytes) -> bool:
    text = attrs.decode("utf-8", errors="replace").lower()
    return "ts" in text or "typescript" in text


class VueParser:
    lang = "vue"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        script_match = _SCRIPT_RE.search(content)
        if script_match is not None:
            attrs = script_match.group(1) or b""
            script_body = script_match.group(2) or b""
            sub_lang = "typescript" if _is_typescript(attrs) else "javascript"
            file_node = parse_js_like(
                content=script_body,
                rel_path=rel_path,
                project_root=project_root,
                file_hash=file_hash,
                lang=sub_lang,
            )
            # Overwrite lang/meta to identify the file as Vue.
            file_node.meta = FileMeta(lang="vue", hash=file_hash, path=rel_path)
        else:
            file_node = FileNode(
                _meta=FileMeta(lang="vue", hash=file_hash, path=rel_path)
            )

        # Components used in the template.
        components: list[str] = []
        seen: set[str] = set()
        tpl_match = _TEMPLATE_RE.search(content)
        if tpl_match is not None:
            for tag in _TAG_RE.findall(tpl_match.group(1) or b""):
                name = tag.decode("utf-8", errors="replace")
                # Heuristic: components are PascalCase or kebab-case with a
                # dash.  Plain lowercase HTML tags are skipped.
                if name in seen:
                    continue
                if name[:1].isupper() or "-" in name:
                    seen.add(name)
                    components.append(name)
        if components:
            file_node.extras["components_used"] = components

        return file_node
