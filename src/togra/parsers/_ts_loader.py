"""Lazily-cached tree-sitter ``Language`` and ``Parser`` instances.

Building a ``Language`` is cheap but non-zero, so we memoise per process.
``tree_sitter.Parser`` is not thread-safe across concurrent ``parse`` calls;
the build pipeline therefore uses thread-local parsers (see ``commands/build.py``).
"""

from __future__ import annotations

from functools import lru_cache

from tree_sitter import Language, Parser


@lru_cache(maxsize=None)
def python_language() -> Language:
    import tree_sitter_python

    return Language(tree_sitter_python.language())


@lru_cache(maxsize=None)
def javascript_language() -> Language:
    import tree_sitter_javascript

    return Language(tree_sitter_javascript.language())


@lru_cache(maxsize=None)
def typescript_language() -> Language:
    import tree_sitter_typescript

    return Language(tree_sitter_typescript.language_typescript())


@lru_cache(maxsize=None)
def tsx_language() -> Language:
    import tree_sitter_typescript

    return Language(tree_sitter_typescript.language_tsx())


def make_parser(language: Language) -> Parser:
    """Return a fresh ``Parser`` bound to ``language``."""
    return Parser(language)
