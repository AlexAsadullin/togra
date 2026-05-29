# togra (Token-Graph)

Offline CLI utility that builds an algorithmic graph of a project's structure
**without calling any LLM**. All `description` fields in the resulting
`togra-output/graph.json` are left empty (`""`) so they can be filled later by
an external AI agent — a separate, controlled step.

- 0 tokens spent at build time
- 0 network calls (everything is parsed locally with `tree-sitter`)
- SHA256-based incremental cache → second build only re-parses changed files

See [`.claude/tech-task.md`](.claude/tech-task.md) for the full specification.

## Install

The package is not on PyPI yet. Install from the local source tree:

```bash
# Editable install (recommended for development — code edits are live)
pip install -e /path/to/togra

# Or a one-shot install of the current state
pip install /path/to/togra

# Or globally via pipx (isolated venv, `togra` available anywhere)
pipx install /path/to/togra
```

Sanity check:

```bash
togra --help
togra --version
```

## Commands

| Command | What it does |
|---------|--------------|
| `togra init` | Create `togra-output/` (cache + manifest) and `.tograignore` (copy of `.gitignore` if present, otherwise a sensible default). |
| `togra build` | Build / update `togra-output/graph.json`. |
| `togra info` | Print cache and last-build statistics. |
| `togra clean` | Drop cached fragments (`--all` removes the whole `togra-output/`). |
| `togra tokens [PATH]` | Approximate Claude-style token count for files, a directory, or the graph. |

### `togra build` flags

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--update` | `-u` | ✓ | Incremental: only files whose SHA256 changed. |
| `--full` | `-f` |   | Ignore cache; rebuild everything. |
| `--newonly` | `-n` |   | Only files absent from the index; modified files keep their cached fragment. |
| `--lang` | `-l` |   | Comma-separated language filter, e.g. `python,typescript`. |
| `--output` | `-o` | `togra-output/graph.json` | Custom graph path. |
| `--output-dir` | `-d` | `togra-output/` | Custom artefacts directory (useful in CI). |
| `--project` | `-p` | `.` | Project root. |
| `--verbose` | `-v` |   | Progress bar + per-stage timings. |
| `--help` | `-h` |   | Show help. |

### `togra tokens` flags

| Flag / Arg | Default | Description |
|------------|---------|-------------|
| `[PATH]` | `.` | File or directory to scan. |
| `--graph` / `-g` |   | Count tokens in `togra-output/graph.json` instead of source. |
| `--lang` / `-l` |   | Language filter, comma-separated. |
| `--project` / `-p` | `.` | Project root (controls `.tograignore` lookup). |
| `--output-dir` / `-d` | `togra-output/` | Used together with `--graph`. |
| `--chars-per-token` | `3.5` | Heuristic ratio — lower means more tokens per char. |
| `--verbose` / `-v` |   | Per-file breakdown table. |
| `--help` / `-h` |   | Show help. |

Token counting is fully offline (no LLM clients, no network). It uses a
length-based heuristic — `ceil(len(text) / 3.5)` by default — which
approximates the Claude tokeniser within roughly 10 % on mixed code +
prose. If you have a better estimate for your corpus, override
`--chars-per-token`.

### `togra clean`

| Flag | Description |
|------|-------------|
| `--all` | Remove the entire `togra-output/` directory (not just the cache). |

## Quick start

```bash
cd my-project
togra init
togra build               # incremental (default)
togra info                # see what was built
togra tokens              # how big is the source corpus?
togra tokens --graph      # how big is the resulting graph?
```

Re-run `togra build` after code changes — only the modified files are
re-parsed.

## Supported languages

| Language | Mode |
|----------|------|
| Python | Full AST parsing (`tree-sitter-python`) — imports, classes, methods, calls. |
| JavaScript / TypeScript / TSX | Full AST parsing. |
| Vue (`*.vue`) | `<template>` → component tags; `<script>` / `<script setup>` parsed as JS or TS. |
| CSS / SCSS / SASS / LESS | Simplified: selectors, `@media`, `@import`, `url(...)`. |
| HTML | Simplified: tags, ids, classes, `<script src>` / `<link href>`. |
| JSON | Simplified: structural `keys_tree`. |
| Anything else | Fallback node with `_meta.path` + empty `description` — no classes/functions/imports. |

## Output layout

After `togra init` your project gains:

```
my-project/
├── .tograignore          # gitignore-style rules
└── togra-output/
    ├── graph.json        # main artefact — all `description` fields are ""
    ├── manifest.json     # version, last-build timestamp, statistics
    └── cache/
        ├── index.json    # {rel_path: {hash, lang, fragment}}
        └── fragments/    # per-file JSON, addressed by content SHA256
```

Recommended `.gitignore`:

```gitignore
# Cache is per-machine — do not commit
togra-output/cache/
# Commit the graph for team sync (optional)
# !togra-output/graph.json
# !togra-output/manifest.json
```

## Workflow with an AI agent

1. `togra build` — generates `graph.json` with structured metadata and empty
   `description` fields. **0 tokens.**
2. Feed `graph.json` to your AI agent and ask it to fill the empty
   `description` fields using the available types, parameters, imports and
   call sites. Token cost stays predictable because the agent never sees
   raw source code.
3. After code changes run `togra build` again — only modified files are
   re-parsed. The agent only refreshes affected descriptions.

## Development

```bash
git clone <this repo>
cd token_graph_for_claudecode
python3.13 -m venv venv
./venv/bin/pip install -e ".[dev]"
./venv/bin/pytest -q
```

## License

MIT. No telemetry, no hidden API calls.
