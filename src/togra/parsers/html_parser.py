"""Simplified HTML parser using :mod:`html.parser` from the stdlib."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from togra.schema import FileMeta, FileNode


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.ids: list[str] = []
        self.classes: list[str] = []
        self.scripts: list[str] = []
        self.links: list[str] = []
        self.structure: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attr_map = {k: v or "" for k, v in attrs}
        if "id" in attr_map:
            self.ids.append(attr_map["id"])
        if "class" in attr_map:
            self.classes.extend(c for c in attr_map["class"].split() if c)
        if tag == "script" and "src" in attr_map:
            self.scripts.append(attr_map["src"])
        if tag == "link" and "href" in attr_map:
            self.links.append(attr_map["href"])

        node: dict[str, Any] = {
            "tag": tag,
            "id": attr_map.get("id", ""),
            "class": attr_map.get("class", ""),
            "children": [],
        }
        if self._stack:
            self._stack[-1]["children"].append(node)
        else:
            self.structure.append(node)
        # Void elements never go on the stack.
        if tag not in {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                break


class HtmlParser:
    lang = "html"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        del project_root
        collector = _Collector()
        try:
            collector.feed(content.decode("utf-8", errors="replace"))
            collector.close()
        except Exception:
            # Malformed HTML — keep whatever we got so far.
            pass
        meta = FileMeta(lang="html", hash=file_hash, path=rel_path)
        node = FileNode(_meta=meta)
        node.extras["tags"] = sorted(set(collector.tags))
        node.extras["ids"] = collector.ids
        node.extras["classes"] = sorted(set(collector.classes))
        if collector.scripts:
            node.extras["scripts"] = collector.scripts
        if collector.links:
            node.extras["links"] = collector.links
        node.extras["structure"] = collector.structure
        return node
