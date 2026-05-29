#  Техническое задание: CLI-утилита `togra` (Token-Graph)

## 1. Введение и Цели
**`togra`** — терминальная CLI-утилита на Python 3.13 для построения алгоритмического графа зависимостей и структуры проекта.

**Ключевое отличие от аналогов:** Полное отсутствие вызовов LLM. Утилита работает исключительно с AST-деревьями (`tree-sitter`), хешированием и файловым обходом.

**Назначение:** Генерация структурированного `graph.json`, где поле `description` остаётся пустым (`""`) для последующего семантического заполнения внешним ИИ-агентом. Это снижает стоимость контекста на 90%+ и исключает зависимость от API-квот.

**Архитектурный принцип:** `togra` устанавливается через `pip` и работает **локально в каждом проекте**. Все артефакты (кэш, граф, метаданные) хранятся в папке `togra-output/` в корне проекта. Это обеспечивает:
- Полную изоляцию проектов (кэш не пересекается)
- Прозрачность: разработчик видит, что создаёт утилита
- Простоту: не нужно управлять глобальным состоянием в `~/.togra/`
- Git-интеграцию: можно коммитить/игнорировать `togra-output/` по необходимости

---

## 2. Стек технологий и Установка

| Компонент | Выбор | Обоснование |
|-----------|-------|-------------|
| **Язык** | Python 3.13 | Современный синтаксис, быстрая работа с `pathlib`, `hashlib`, `json` |
| **CLI-фреймворк** | `typer` + `rich` | Декларативное описание команд, автоматическая генерация `--help`, красивая таблица прогресса |
| **Парсинг кода** | `tree-sitter` + грамматики | Быстрый AST-анализ без отправки кода наружу. Поддержка Python, JS/TS, CSS, HTML, Vue, JSON |
| **Валидация схемы** | `pydantic` | Строгая типизация выходного JSON, авто-документация полей |
| **Системные утилиты** | StdLib (`pathlib`, `hashlib`, `json`, `concurrent.futures`) | Минимальный оверхед, отсутствие внешних зависимостей для кэша/обхода |

### Установка через pip3
```bash
# Установка из PyPI (после публикации)
pip3 install togra

# Или установка из исходников
pip3 install git+https://github.com/yourusername/togra.git

# Проверка установки
togra --help
```

### pyproject.toml (фрагмент)
```toml
[project]
name = "togra"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "tree-sitter>=0.21.0",
    "tree-sitter-python>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
    "pydantic>=2.0.0",
]

[project.scripts]
togra = "togra.cli:app"
```

> **Отказ от излишеств:** `networkx`, `graspologic`, LLM-клиенты, тяжелые ML-библиотеки исключены. Граф хранится в виде вложенного JSON-дерева, а не объекта в памяти.

---

## 3. CLI Интерфейс

### Базовая команда
```bash
togra [COMMAND] [OPTIONS]
```

### Команды
| Команда | Описание |
|---------|----------|
| `togra init` | Инициализация проекта. Создаёт `.tograignore` (копирует `.gitignore` или пустой), проверяет наличие `.git`, создаёт папку `togra-output/`. |
| `togra build` | Основная команда построения графа. Сканирует проект, использует кэш из `togra-output/cache/`, генерирует `togra-output/graph.json`. |
| `togra info` | Вывод статистики: кол-во файлов, хешей в кэше, размер графа, время последнего обновления. |
| `togra clean` | Очистка кэша и временных файлов в `togra-output/`. `--all` удаляет всю папку. |

### Флаги (применимы к `build`)
| Флаг | Алиас | Описание |
|------|-------|----------|
| `--update` | `-u` | **По умолчанию.** Инкрементальное обновление: обрабатывает только файлы с изменённым SHA256. |
| `--full` | `-f` | Полный пересчёт. Игнорирует кэш, перестраивает граф с нуля. |
| `--newonly` | `-n` | Строго новые файлы. Не обновляет изменённые, только добавляет отсутствующие в индексе. |
| `--output` | `-o` | Путь к выходному файлу. По умолчанию: `./togra-output/graph.json`. |
| `--output-dir` | `-d` | Путь к папке вывода. По умолчанию: `./togra-output/`. Позволяет переопределить расположение артефактов. |
| `--lang` | `-l` | Фильтр по языку. Пример: `--lang python,typescript`. |
| `--verbose` | `-v` | Логирование каждого этапа, тайминги парсинга, список пропущенных файлов. |
| `--help` | `-h` | Показать справку по команде и доступным опциям. |

### Примеры использования
```bash
# Инициализация проекта
togra init

# Построение графа (инкрементально, по умолчанию)
togra build

# Полный пересчёт
togra build --full

# Только новые файлы
togra build --newonly

# Построить только для Python и TypeScript
togra build --lang python,typescript

# Вывод подробной информации
togra info --verbose

# Изменить папку вывода (например, для CI)
togra build --output-dir ./artifacts/togra/
```

---

## 4. Поддерживаемые языки и Правила парсинга

Утилита использует `tree-sitter` для каждого языка. Ниже таблица соответствия AST-узлов полям графа.

| Язык | Классы/Типы | Функции/Методы | Импорт/Зависимости | Особенности |
|------|-------------|----------------|-------------------|-------------|
| **Python 3** | `class_definition` | `function_definition`, `async_function_definition` | `import_statement`, `from_import_statement` | Декораторы (`@`), аннотации типов, `self`-атрибуты из `__init__` |
| **JavaScript** | `class_declaration` | `function_declaration`, `arrow_function` | `import_statement`, `require_call` | Динамические импорты `import()` помечаются как `lazy` |
| **TypeScript** | `class_declaration`, `interface_declaration`, `type_alias_declaration` | `function_declaration` + `type_annotation` | `import_statement` | Учитываются `export type`, дженерики сохраняются в `returns.type` |
| **Vue (.vue)** | `script_setup` → маппинг на TS/JS правила | `script_setup` функции | `import` внутри `<script>` | `<template>` теги сохраняются как `components_used` |
| **CSS** | Не поддерживается (заменяется на `selectors`) | Не поддерживается | `@import`, `url()` | Хранится как `selectors`: list of `.class`, `#id`, `@media` |
| **HTML** | Не поддерживается (заменяется на `tags`) | Не поддерживается | `<script src>`, `<link href>` | Хранится как `structure`: вложенность тегов + атрибуты `id/class` |
| **JSON** | Не парсится глубоко | | | Упрощается до `keys_tree` и пустого `description` |

> **Правило для JSON/CSS/HTML:** Для этих форматов структура упрощается. Вместо `classes/functions` сохраняются метаданные формата, чтобы не ломать схему, но не тратить ресурсы на бессмысленный AST-обход.

---

## 5. Структура Графа (`graph.json`)

Граф представляет собой **файловое дерево**, где каждый узел содержит алгоритмически извлечённые метаданные. Поле `description` всегда равно `""`.

```json
{
  "project_root": {
    "_meta": { "type": "directory", "path": "." },
    "src": {
      "_meta": { "type": "directory" },
      "auth": {
        "_meta": { "type": "directory" },
        "login.py": {
          "_meta": { 
            "type": "file", 
            "lang": "python", 
            "hash": "sha256:a1b2c3...", 
            "tags": ["core"],
            "last_updated": "2024-05-20T10:00:00Z"
          },
          "description": "", 
          
          "imports": {
            "external": [
              { "lib": "fastapi", "items": ["APIRouter", "Depends"] }
            ],
            "internal": [
              { "name": "User", "type": "class", "source_path": "../models/user.py" },
              { "name": "hash_password", "type": "function", "source_path": "../utils/crypto.py" },
              { "name": "APP_CONFIG", "type": "constant", "source_path": "../config/settings.py" }
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
                    { "name": "validate_input", "source_path": "self" }
                  ],
                  "calls_external": [
                    { "name": "User.get_by_name", "source_path": "../models/user.py" }
                  ]
                }
              }
            }
          },

          "functions": {
            "get_current_user": {
              "description": "",
              "decorators": ["@Depends"],
              "parameters": [
                { "name": "token", "type": "str" }
              ],
              "returns": { "type": "User" }
            }
          }
        }
      }
    }
  }
}
```

### Ключевые особенности схемы:
1. **Файловая иерархия:** Граф повторяет структуру папок. `path` в `_meta` всегда относителен к корню.
2. **Явные связи:** `imports.internal` и `calls_*` содержат `source_path`. Это позволяет строить граф рёбер без эвристик.
3. **Пустые описания:** `description: ""` везде. Заполнение — задача внешнего ИИ-конвейера.
4. **Мета-данные:** `hash`, `lang`, `tags`, `last_updated` для отладки и инкрементальности.

---

## 6. Алгоритмы: Построение, Обход и Кэширование

### 6.1. Общий пайплайн построения графа

```
┌─────────────────────────────────┐
│ 1. COLLECT: Обход файловой системы │
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 2. FILTER: .tograignore + расширения│
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 3. HASH: SHA256 для каждого файла  │
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 4. DIFF: Сравнение с кэш-индексом  │
│    (togra-output/cache/index.json)│
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 5. PARSE: tree-sitter для dirty-файлов│
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 6. EXTRACT: AST → узлы/рёбра       │
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 7. RESOLVE: Разрешение путей импортов│
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 8. BUILD_CALLS: Анализ вызовов функций│
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 9. MERGE: Сборка фрагментов в граф  │
└─────────┬───────────────────────┘
          ▼
┌─────────────────────────────────┐
│ 10. WRITE: Атомарная запись graph.json│
│     в togra-output/graph.json   │
└─────────────────────────────────┘
```

---

### 6.2. Алгоритм сбора файлов (`collect_files`)

```python
def collect_files(root: Path, ignore_patterns: list[str], extensions: set[str]) -> list[Path]:
    """
    Рекурсивный обход с фильтрацией.
    Сложность: O(n), где n — количество файлов в дереве.
    """
    result = []
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix not in extensions:
            continue
        if matches_ignore_pattern(file.relative_to(root), ignore_patterns):
            continue
        # Исключаем саму папку вывода из сканирования
        if file.is_relative_to(root / "togra-output"):
            continue
        result.append(file)
    return result
```

**Оптимизации:**
- Используется `rglob()` с ленивым итератором — не загружает всё в память сразу
- Фильтрация по расширению происходит до проверки `.tograignore` (быстрее)
- Поддержка `**/`, `*.ext`, `!negation` в `.tograignore` через `pathspec` или кастомный парсер
- Автоматическое исключение `togra-output/` из обхода (защита от рекурсии)

---

### 6.3. Алгоритм хеширования и кэширования

```python
def compute_file_hash(path: Path) -> str:
    """SHA256 хеш содержимого файла."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
```

**Структура кэша (в корне проекта `togra-output/cache/`):**
```
project-root/
├── src/
├── tests/
├── togra-output/          ← создаётся при togra init
│   ├── graph.json         # Основной выход: структурированный граф
│   ├── cache/
│   │   ├── index.json     # { "src/auth/login.py": {"hash": "...", "lang": "py", "fragment": "frag/abc123.json"} }
│   │   └── fragments/
│   │       ├── abc123.json     # JSON-фрагмент для файла с хешом abc123
│   │       └── def456.json
│   └── manifest.json      # Метаданные сборки: версия togra, timestamp, статистика
```

**Алгоритм инкрементального обновления (`--update`):**
```python
def get_dirty_files(files: list[Path], cache_index: dict, output_dir: Path) -> dict[str, str]:
    """
    Возвращает словарь {rel_path: new_hash} для файлов, требующих перепарсинга.
    """
    dirty = {}
    for file in files:
        rel_path = str(file.relative_to(project_root))
        new_hash = compute_file_hash(file)
        cached = cache_index.get(rel_path)
        
        if not cached or cached["hash"] != new_hash:
            dirty[rel_path] = new_hash
    
    return dirty
```

**Алгоритм загрузки фрагмента:**
```python
def load_fragment(rel_path: str, cache_index: dict, output_dir: Path) -> dict | None:
    """Загружает фрагмент из кэша или None, если не найден."""
    entry = cache_index.get(rel_path)
    if not entry:
        return None
    fragment_path = output_dir / "cache" / "fragments" / entry["fragment"]
    if not fragment_path.exists():
        return None
    return json.loads(fragment_path.read_text())
```

**Инициализация кэша при `togra init`:**
```python
def init_cache(output_dir: Path):
    """Создаёт структуру папок и пустой индекс кэша."""
    cache_dir = output_dir / "cache" / "fragments"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    index_path = output_dir / "cache" / "index.json"
    if not index_path.exists():
        index_path.write_text("{}")  # пустой индекс
    
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps({
            "version": __version__,
            "created_at": datetime.now().isoformat(),
            "project_root": str(project_root)
        }, indent=2))
```

---

### 6.4. Алгоритм AST-экстракции (`extract_from_ast`)

Для каждого поддерживаемого языка определяется маппинг AST-узлов → поля графа.

**Пример для Python (псевдокод на основе tree-sitter):**
```python
def extract_python(file_content: str, file_path: Path, project_root: Path) -> FileNode:
    parser = Parser()
    parser.set_language(Python.language())
    tree = parser.parse(file_content.encode())
    root = tree.root_node
    
    node = FileNode(
        meta=FileMeta(lang="python", hash=compute_hash(file_content)),
        imports=extract_imports(root),
        classes=extract_classes(root),
        functions=extract_functions(root)
    )
    
    # Пост-процессинг: разрешение относительных путей
    resolve_internal_imports(node, file_path, project_root)
    
    return node
```

**Извлечение импортов:**
```python
def extract_imports(root_node) -> Imports:
    external = []
    internal = []
    
    for import_stmt in root_node.named_children:
        if import_stmt.type == "import_statement":
            # import module
            lib_name = import_stmt.child_by_field_name("name").text.decode()
            external.append({"lib": lib_name, "items": []})
        
        elif import_stmt.type == "from_import_statement":
            # from module import name
            module = import_stmt.child_by_field_name("module_name").text.decode()
            names = [alias.text.decode() for alias in import_stmt.child_by_field_name("name")]
            
            if is_external_lib(module):
                external.append({"lib": module, "items": names})
            else:
                for name in names:
                    internal.append({
                        "name": name,
                        "type": resolve_import_type(name, module),  # class/function/constant
                        "source_path": resolve_relative_path(module, current_file)
                    })
    
    return Imports(external=external, internal=internal)
```

**Определение типа импортируемого объекта:**
```python
def resolve_import_type(name: str, module_path: str) -> str:
    """
    Эвристическое определение типа:
    - UPPER_CASE → constant
    - CamelCase → class
    - snake_case → function/variable
    - Требует анализа целевого файла или fallback на "unknown"
    """
    if name.isupper():
        return "constant"
    elif name[0].isupper() and "_" not in name:
        return "class"
    else:
        return "function"  # fallback
```

---

### 6.5. Алгоритм разрешения путей (`resolve_internal_imports`)

```python
def resolve_relative_path(import_module: str, current_file: Path, project_root: Path) -> str:
    """
    Преобразует относительный импорт в путь к файлу относительно project_root.
    
    Примеры:
    - "from .models import User" + "src/auth/login.py" → "src/models/user.py"
    - "from ..utils import helper" + "src/auth/login.py" → "src/utils/helper.py"
    """
    current_dir = current_file.parent
    parts = import_module.split(".")
    
    # Обработка относительных импортов (. и ..)
    if parts[0] == "":
        parts = parts[1:]  # убрать пустой элемент после точки
    while parts and parts[0] == "..":
        current_dir = current_dir.parent
        parts = parts[1:]
    
    # Сборка пути
    target_path = current_dir / "/".join(parts)
    
    # Попытка найти файл с разными расширениями
    for ext in [".py", ".ts", ".js", ".vue"]:
        candidate = target_path.with_suffix(ext)
        if candidate.exists():
            return str(candidate.relative_to(project_root))
    
    # Fallback: вернуть как есть
    return import_module
```

---

### 6.6. Алгоритм построения графа вызовов (`build_call_graph`)

```python
def extract_calls(method_node, file_node: FileNode, current_file: Path) -> list[CallRef]:
    """
    Находит вызовы функций/методов внутри тела метода.
    
    Возвращает список объектов:
    - { "name": "func_name", "source_path": "self" | "path/to/file.py" }
    """
    calls = []
    
    for call_expr in method_node.named_descendants:
        if call_expr.type == "call":
            func_name = extract_call_name(call_expr)
            
            if is_local_call(func_name, file_node):
                calls.append({"name": func_name, "source_path": "self"})
            else:
                # Поиск в импортированных модулях
                target_file = find_import_source(func_name, file_node.imports.internal)
                if target_file:
                    calls.append({"name": func_name, "source_path": target_file})
    
    return calls
```

**Оптимизация:** Поиск вызовов ограничивается телом метода, не обходит весь файл. Используется кэш импортов для быстрого разрешения `func_name → source_path`.

---

### 6.7. Алгоритм слияния фрагментов в граф (`merge_fragments`)

```python
def build_graph_tree(dirty_files: dict[str, str], cache_index: dict, project_root: Path, output_dir: Path) -> dict:
    """
    Собирает финальное дерево графа из кэшированных и новых фрагментов.
    """
    graph = {"project_root": {"_meta": {"type": "directory", "path": "."}}}
    
    for rel_path, new_hash in dirty_files.items():
        # 1. Парсинг нового файла
        file_content = (project_root / rel_path).read_text()
        fragment = parse_file(file_content, rel_path)
        fragment["_meta"]["hash"] = new_hash
        
        # 2. Сохранение в кэш (в togra-output/cache/)
        save_to_cache(rel_path, new_hash, fragment, output_dir)
        
        # 3. Вставка в дерево
        insert_into_tree(graph, rel_path, fragment)
    
    # 4. Загрузка чистых файлов из кэша
    for rel_path in cache_index.keys() - dirty_files.keys():
        fragment = load_fragment(rel_path, cache_index, output_dir)
        if fragment:
            insert_into_tree(graph, rel_path, fragment)
    
    return graph
```

**Функция `insert_into_tree`:**
```python
def insert_into_tree(graph: dict, rel_path: str, fragment: dict):
    """Вставляет фрагмент в правильное место файлового дерева."""
    parts = Path(rel_path).parts
    current = graph["project_root"]
    
    # Навигация по директориям
    for part in parts[:-1]:
        if part not in current:
            current[part] = {"_meta": {"type": "directory"}}
        current = current[part]
    
    # Вставка файла
    filename = parts[-1]
    current[filename] = fragment
```

---

### 6.8. Алгоритмы обхода графа (для внешних ИИ-агентов)

Хотя `togra` не выполняет семантический анализ, она предоставляет структуру, удобную для обхода внешними системами.

**Поиск пути между сущностями (BFS):**
```python
def find_path(graph: dict, start_entity: str, target_entity: str) -> list[str] | None:
    """
    Находит путь между двумя сущностями через imports/calls связи.
    Возвращает список файлов на пути или None.
    """
    from collections import deque
    
    # Построение обратного индекса: entity_name → [file_paths]
    entity_index = build_entity_index(graph)
    
    if start_entity not in entity_index or target_entity not in entity_index:
        return None
    
    queue = deque([(entity_index[start_entity][0], [entity_index[start_entity][0]])])
    visited = set()
    
    while queue:
        current_file, path = queue.popleft()
        if current_file in visited:
            continue
        visited.add(current_file)
        
        # Проверка: содержит ли файл целевую сущность
        if target_entity in get_entities_in_file(graph, current_file):
            return path
        
        # Добавление соседних файлов через imports.internal
        for import_ref in get_internal_imports(graph, current_file):
            if import_ref["source_path"] not in visited:
                queue.append((import_ref["source_path"], path + [import_ref["source_path"]]))
    
    return None
```

**Поиск "божественных узлов" (высокая связность):**
```python
def find_god_nodes(graph: dict, threshold: int = 10) -> list[str]:
    """
    Находит файлы с количеством внутренних импортов/экспортов > threshold.
    """
    god_nodes = []
    
    def count_connections(node: dict) -> int:
        if "_meta" in node and node["_meta"]["type"] == "file":
            imports = node.get("imports", {}).get("internal", [])
            # + обратные ссылки (кто импортирует этот файл)
            return len(imports)
        return 0
    
    def traverse(node: dict, path: str = ""):
        if "_meta" in node and node["_meta"]["type"] == "file":
            if count_connections(node) > threshold:
                god_nodes.append(path)
        for key, value in node.items():
            if key == "_meta":
                continue
            traverse(value, f"{path}/{key}" if path else key)
    
    traverse(graph["project_root"])
    return god_nodes
```

---

### 6.9. Атомарная запись и безопасность

```python
def atomic_write_json(path: Path, data: dict):
    """Записывает JSON атомарно: сначала в .tmp, затем переименование."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_path.rename(path)  # Атомарная операция на большинстве ФС
```

**Преимущества:**
- Защита от повреждения `graph.json` при прерывании процесса
- Совместимость с `git`: файл всегда в консистентном состоянии
- Расположение в `togra-output/` позволяет легко игнорировать или коммитить артефакты

---

## 7. Хранение истории и интеграция с Git

### 7.1. Локальное хранение в проекте
- **Кэш** хранится в корне проекта: `togra-output/cache/`
- **`graph.json`** генерируется в: `togra-output/graph.json`
- **`manifest.json`** содержит метаданные сборки: версия `togra`, дата, статистика
- **История версий графа** отслеживается через `git commit` самого `graph.json`

### 7.2. Рекомендуемый `.gitignore`
```gitignore
# Кэш togra — локальный, не коммитить (занимает место, привязан к машине)
togra-output/cache/

# Граф — коммитить для синхронизации команды (опционально)
# !togra-output/graph.json
# !togra-output/manifest.json

# Если не хотите коммитить граф вообще:
togra-output/
```

### 7.3. Workflow с историей
```bash
# После изменения кода
git add src/
git commit -m "feat: add auth module"

# Обновить граф (инкрементально)
togra build --update

# Закоммитить обновлённый граф (опционально)
git add togra-output/graph.json
git commit -m "chore: update graph after auth module"
```

**Преимущества:**
- История изменений графа привязана к истории кода
- Разработчики видят, как менялась структура проекта
- Легко откатить граф к любой версии через `git checkout`
- Кэш не коммитится → каждый разработчик строит свой локальный кэш

### 7.4. Командная работа
```bash
# Разработчик А:
togra init          # создаёт togra-output/
togra build         # строит граф, заполняет кэш

# Коммитит только граф (не кэш):
git add togra-output/graph.json
git commit -m "chore: add initial graph"

# Разработчик Б (клонирует репо):
git pull
togra build --update  # использует graph.json, строит свой локальный кэш
```

---

## 8. Workflow и Интеграция с ИИ

1. **Разработчик:** `togra init` → `togra build`
2. **Утилита:** Генерирует `togra-output/graph.json` за 2-10 сек (зависит от размера проекта). Расход токенов: **0**.
3. **ИИ-Агент:** 
   - Читает `togra-output/graph.json` в контекст.
   - Запускает промпт: *"Заполни пустые поля `description`, используя типы, параметры, импорты и вызовы. Не читай исходный код."*
   - Сохраняет обогащённый граф или использует его для ответов.
4. **Обновление:** После коммита → `togra build --update`. Пересчитываются только изменённые файлы. ИИ обновляет только затронутые `description`.

> **Экономика:** Первичный билд = 0 токенов. Обновление = 0 токенов. Заполнение описаний = ~10-20% от стоимости анализа сырого кода, так как ИИ работает со структурированным JSON, а не с тысячами строк кода.

---

## 9. Технические ограничения и Безопасность

| Аспект | Политика `togra` |
|--------|------------------|
| **Сетевые запросы** | Запрещены. Утилита работает полностью оффлайн. |
| **Исходный код** | Не отправляется наружу. Парсинг локальный. |
| **Кэш** | 📁 Хранит только хеши и структурированные фрагменты. Исходный код не сохраняется. |
| `.tograignore` | Синтаксис совместим с `.gitignore`. Поддерживает `!negation`, `**/`, `*.ext`. |
| **Расположение артефактов** | 📁 Всё в `togra-output/` в корне проекта. Никаких глобальных папок в `~/.` |
| **Лицензия/Приватность** | MIT. Никакой телеметрии, никаких скрытых вызовов API. |

---

## 10. Чеклист реализации (MVP)

- [ ] Настройка `pyproject.toml` (Python 3.13, typer, tree-sitter, pydantic)
- [ ] CLI scaffold: `togra init`, `togra build`, флаги `--update/--full/--newonly/--copy-gitignore (копирует содержимое .gitignore в .tograignore, если не найдет gitignore - предупреждение)/--output-dir/--help`
- [ ] Парсеры `tree-sitter` для Python, JS/TS, Vue
- [ ] Модуль кэширования: `index.json` + `fragments/` + SHA256 diff (в `togra-output/cache/`)
- [ ] Сборщик графа: мердж фрагментов в файловое дерево, разрешение путей
- [ ] Алгоритм `build_call_graph`: анализ вызовов функций внутри методов
- [ ] Валидатор схемы через `pydantic`
- [ ] Атомарная запись `graph.json` в `togra-output/`
- [ ] Функция `init_cache()`: создание структуры папок при `togra init`
- [ ] Исключение `togra-output/` из сканирования (защита от рекурсии)
- [ ] Тесты: фикстуры с разными языками, проверка инкрементальности, проверка пустых `description`
- [ ] Документация: `README.md` с примерами workflow + интеграции с внешними ИИ

---

## 11. Структура проекта после `togra init`

```
my-project/
├── src/
│   ├── auth/
│   │   └── login.py
│   └── utils/
│       └── helpers.py
├── tests/
├── .git/
├── .gitignore
├── .tograignore          ← создаётся: правила исключения файлов
└── togra-output/         ← создаётся: все артефакты togra
    ├── graph.json        # Основной выход: структурированный граф проекта
    ├── cache/
    │   ├── index.json    # Индекс: {rel_path: {hash, lang, fragment}}
    │   └── fragments/    # Фрагменты графа по хешам
    └── manifest.json     # Метаданные: версия, дата, статистика сборки
```

### Содержимое `.tograignore` (по умолчанию):
```
# Синтаксис как в .gitignore
# Исключить служебные папки
node_modules/
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
env/

# Исключить медиа и логи
*.log
*.tmp
*.swp
*.swo

```

---