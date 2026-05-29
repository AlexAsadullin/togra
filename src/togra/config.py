"""Constants and language/extension mappings."""

from __future__ import annotations

# Output layout (per tech-task.md §6.3, §11)
OUTPUT_DIR_NAME = "togra-output"
GRAPH_FILENAME = "graph.json"
MANIFEST_FILENAME = "manifest.json"
CACHE_DIRNAME = "cache"
CACHE_INDEX_FILENAME = "index.json"
FRAGMENTS_DIRNAME = "fragments"
IGNORE_FILENAME = ".tograignore"
AGENT_GUIDE_FILENAME = "AGENT_GUIDE.md"

# Extension → canonical language id.
# Languages "python" and "vue" use full AST parsing; "javascript"/"typescript"
# are used standalone and also internally by the Vue parser.  "css", "html",
# "json" use simplified extraction.  Anything else falls through to the
# fallback parser.
EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".less": "css",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(EXTENSION_TO_LANG.keys())

# Default .tograignore content (tech-task §11)
DEFAULT_TOGRAIGNORE = """# Synthesised by `togra init`.
# Syntax: same as .gitignore.
node_modules/
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
env/

*.log
*.tmp
*.swp
*.swo
"""
