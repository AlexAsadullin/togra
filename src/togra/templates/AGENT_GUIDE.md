# Guide for the description-filling agent

`togra build` produces `togra-output/graph.json` with every `description`
field set to `""`. Your job is to fill those fields — and **only** those
fields — using the structured metadata already present in the graph.

Graph does not provide the entire source code. You are given names, types, parameters,
imports, and call sites. Infer purpose from those signals.

---

## 1. Graph format at a glance

The graph is a **nested file tree** rooted at `project_root`. Directories
and files are siblings keyed by name; metadata lives under `_meta`.

```jsonc
{
  "project_root": {
    "_meta": { "type": "directory", "path": "." },
    "src": {
      "_meta": { "type": "directory", "path": "src" },
      "auth": {
        "_meta": { "type": "directory", "path": "src/auth" },
        "login.py": {
          "_meta": {
            "type": "file",
            "lang": "python",
            "hash": "sha256:…",
            "path": "src/auth/login.py",
            "tags": [],
            "last_updated": "2026-05-29T15:00:00Z"
          },
          "description": "",
          "imports": {
            "external": [
              { "lib": "fastapi", "items": ["APIRouter", "Depends"] }
            ],
            "internal": [
              { "name": "User", "type": "class",
                "source_path": "src/models/user.py" },
              { "name": "hash_password", "type": "function",
                "source_path": "src/utils/crypto.py" },
              { "name": "APP_CONFIG", "type": "constant",
                "source_path": "src/config/settings.py" }
            ]
          },
          "classes": {
            "AuthService": {
              "description": "",
              "parents": ["BaseService"],
              "decorators": ["@singleton"],
              "attributes": [
                { "name": "db_session", "type": "Session" },
                { "name": "cache", "type": "RedisClient" }
              ],
              "methods": {
                "authenticate": {
                  "description": "",
                  "decorators": ["@retry"],
                  "parameters": [
                    { "name": "username", "type": "str" },
                    { "name": "password", "type": "str" }
                  ],
                  "returns": { "type": "AuthResult" },
                  "calls_internal": [
                    { "name": "self.validate_input", "source_path": "self" },
                    { "name": "User.get_by_name",
                      "source_path": "src/models/user.py" }
                  ],
                  "calls_external": []
                }
              }
            }
          },
          "functions": {
            "get_current_user": {
              "description": "",
              "decorators": ["@Depends"],
              "parameters": [{ "name": "token", "type": "str" }],
              "returns": { "type": "User" },
              "calls_internal": [],
              "calls_external": []
            }
          }
        }
      }
    }
  }
}
```

Simplified parsers (CSS, HTML, JSON) and the fallback parser emit a thinner
shape — see §3.

---

## 2. Field reference

### Directory node

| Field | Meaning |
|---|---|
| `_meta.type` | Always `"directory"`. |
| `_meta.path` | Project-relative POSIX path of this directory. |
| *(children)* | Sub-directories and files keyed by name. |

Directories themselves do not have a `description` — you only fill leaves
(files and the entities inside them).

### File node — common envelope

| Field | Meaning |
|---|---|
| `_meta.type` | `"file"`. |
| `_meta.lang` | Canonical language id (`python`, `javascript`, `typescript`, `vue`, `css`, `html`, `json`, or `unknown`). |
| `_meta.hash` | SHA256 of the file's bytes — identity, not for prose. |
| `_meta.path` | Project-relative POSIX path. |
| `_meta.tags` | Free-form tags (often empty). |
| `_meta.last_updated` | ISO timestamp of the last parse — ignore for descriptions. |
| `description` | **You fill this.** A short, file-level summary (rules in §4). |
| `imports.external` | Third-party modules: `{ "lib": <pkg>, "items": [<names>] }`. |
| `imports.internal` | Project-local imports with resolved `source_path`. |
| `classes` | Map `class name → ClassNode`. |
| `functions` | Map `function name → FunctionNode`. |
| `extras` *(may be absent)* | Bag for simplified parsers (CSS/HTML/JSON). |

### ClassNode

| Field | Meaning |
|---|---|
| `description` | **You fill this.** What the class represents. |
| `parents` | Base classes / interfaces. |
| `decorators` | Decorators applied to the class declaration. |
| `attributes` | List of `{ name, type }` — instance/class attributes. |
| `methods` | Map `method name → FunctionNode`. |

### FunctionNode (also used for methods)

| Field | Meaning |
|---|---|
| `description` | **You fill this.** What the function/method does. |
| `decorators` | Applied decorators (`@retry`, `@property`, …). |
| `parameters` | List of `{ name, type }`. Types may be empty strings. |
| `returns.type` | Return-type string (may be empty). |
| `calls_internal` | Calls to project-local symbols. `source_path == "self"` means same file. |
| `calls_external` | Calls to third-party / built-in symbols (no resolved path). |

### Import entries

| Object | Fields |
|---|---|
| `imports.external[i]` | `lib` — package name; `items` — imported symbols. |
| `imports.internal[i]` | `name`, `type` (`class` / `function` / `constant` / `module`), `source_path` — project-relative POSIX path to the target file. |

You do **not** add descriptions inside `imports` entries — descriptions
live on the imported entity in its **own** file node.

### Simplified parsers (only `_meta`, `description`, `extras`)

| Language | Notable `extras` keys |
|---|---|
| `css` | `selectors`, `media_queries`, `imports_css`, `urls`. |
| `html` | `tags`, `ids`, `classes`, `scripts`, `links`, `structure`. |
| `json` | `keys_tree` (or `parse_error`). |
| `unknown` (fallback) | none — only `_meta` + `description`. |

For these files you fill only the file-level `description`.

---

## 3. Reading the graph efficiently

- The graph is the entire context — there is no source code to consult.
- Cross-file relations live in `imports.internal[*].source_path` and
  `calls_internal[*].source_path`. Use these to look up the *target* node
  by walking the tree.
- `source_path == "self"` in `calls_internal` means the call resolves
  inside the same file (top-level function or `self.<method>`).
- Items in `calls_external` have empty `source_path` — treat them as black
  boxes; do not invent behaviour.
- Order matters only inside `parameters`. Everything else is a set.

---

## 4. How to write descriptions

### Hard rules

1. **Modify only `description` fields.** Do not add keys, do not edit
   `_meta`, `imports`, `classes`, `methods`, `functions`, `parameters`,
   `returns`, `calls_*`, `extras`. Do not rename anything.
2. **One short paragraph, no markdown, no code fences.** Plain text.
3. **No hedging or filler.** Skip phrases like *"this function probably"*,
   *"it might"*, *"as the name suggests"*. State the purpose directly.
4. **No quoting of identifiers.** Refer to the entity by name without
   backticks or quotes.
5. **No invented behaviour.** If signals are insufficient, write a brief
   description grounded only in name + types; do not extrapolate calls or
   side effects that aren't in the graph.
6. **No leakage between files.** A description must stand on its own —
   readers should understand it without opening the imported targets.

### Length and granularity

| Node | Target length | Focus |
|---|---|---|
| Function / method | 1 sentence (≈ 8–25 words) | What it does + what it returns. Mention key side effects only if visible in `calls_*` / decorators. |
| Class | 1 sentence (≈ 10–30 words) | What it represents and its primary responsibility. Do not list its methods. |
| File | 1–2 sentences (≈ 15–40 words) | Role of the file as a whole. |

### File description rule (important)

The file's `description` MUST be **shorter than the combined length of all
descriptions of its classes, methods, and functions**, and must not repeat
any of them verbatim.

- Think of the file description as a **headline**, not a recap.
- State the file's *role* in the project, not the catalogue of what's
  inside. Example for an `auth/login.py`: *"Login surface for the auth
  module: wires HTTP routes to the AuthService and returns the current
  user from a bearer token."* — it doesn't list `AuthService.authenticate`
  or `get_current_user` mechanics; those are described on their own
  nodes.
- Concretely: before saving, check that
  `len(file.description) < sum(len(d) for d in all_inner_descriptions)`
  **and** that no inner description appears as a substring of the file
  description (or vice-versa).
- If the file is empty (no classes / functions, e.g. `__init__.py`),
  describe its packaging role in one short clause.

### Style guidance

- Lead with a verb for functions/methods ("Authenticate a user…",
  "Compute…", "Render…"). Lead with a noun phrase for classes
  ("Service that…", "Builder for…").
- Mention notable decorators only when they change semantics
  (`@retry`, `@cached`, `@property`, `@singleton`).
- Prefer concrete domain vocabulary inferred from imports
  (`fastapi` → "HTTP route", `redis` → "cache", `sqlalchemy` → "DB
  session") over generic phrasing.
- Use the project's natural language. If filenames and identifiers are in
  English, write descriptions in English. If they are in Russian, write
  in Russian.

### Worked example

Given the `authenticate` method in §1, a good description is:

> Authenticate the given username/password against the user store and
> return an AuthResult; retries transient failures via the @retry policy.

Bad descriptions:

- "This method authenticates." — too generic.
- "Calls self.validate_input then User.get_by_name and returns AuthResult." — restates `calls_internal`, no semantics.
- "Probably checks the password." — hedging.

---

## 5. Output contract

- Produce the **same JSON document** with `description` fields filled.
- Preserve key order and indentation.
- Do not introduce trailing whitespace or comments.
- After filling, the JSON must still validate against the original schema
  (no extra keys, all required fields intact).
- Idempotency: re-running you on an already-filled graph will leave it
  unchanged — never rewrite a non-empty `description` unless explicitly
  asked.

---

## 6. Checklist before you return the result

- [ ] Every previously-empty `description` is now a non-empty string.
- [ ] No other field was modified.
- [ ] No description contains markdown, code fences, or quoted identifiers.
- [ ] File descriptions are shorter than the sum of their inner
      descriptions, and do not duplicate them verbatim.
- [ ] No description fabricates behaviour absent from the graph.
- [ ] Output is still valid JSON.
