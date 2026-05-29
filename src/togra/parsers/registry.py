"""Parser registry: maps extensions / language ids to concrete parsers."""

from __future__ import annotations

from togra.config import EXTENSION_TO_LANG
from togra.parsers.base import Parser
from togra.parsers.css_parser import CssParser
from togra.parsers.fallback import FallbackParser
from togra.parsers.html_parser import HtmlParser
from togra.parsers.js_ts_parser import JavaScriptParser, TypeScriptParser
from togra.parsers.json_parser import JsonParser
from togra.parsers.python_parser import PythonParser
from togra.parsers.vue_parser import VueParser

_BY_LANG: dict[str, Parser] = {
    "python": PythonParser(),
    "javascript": JavaScriptParser(),
    "typescript": TypeScriptParser(),
    "vue": VueParser(),
    "css": CssParser(),
    "html": HtmlParser(),
    "json": JsonParser(),
}

_FALLBACK = FallbackParser()


def lang_for_path(rel_path: str) -> str:
    """Return the canonical lang id for ``rel_path`` or ``"unknown"``."""
    suffix = ""
    dot = rel_path.rfind(".")
    if dot != -1:
        suffix = rel_path[dot:].lower()
    return EXTENSION_TO_LANG.get(suffix, "unknown")


def parser_for_lang(lang: str) -> Parser:
    """Look up the parser for a language id.

    Unknown languages get the fallback parser, which emits a path-only node.
    """
    return _BY_LANG.get(lang, _FALLBACK)
