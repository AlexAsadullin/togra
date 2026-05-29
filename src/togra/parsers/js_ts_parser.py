"""JavaScript / TypeScript parser.

We extract enough structure to satisfy tech-task §4 while keeping the code
simple — top-level declarations, imports, and call sites inside functions
and methods.  Full type-inference would require a TypeScript compiler;
``togra`` deliberately stays on the lexical level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from tree_sitter import Language, Node

from togra.parsers._ts_loader import (
    javascript_language,
    make_parser,
    tsx_language,
    typescript_language,
)
from togra.resolve.imports import resolve_import_type
from togra.schema import (
    ClassNode,
    ExternalImport,
    FileMeta,
    FileNode,
    FunctionNode,
    Imports,
    InternalImport,
    Parameter,
    ReturnSpec,
    CallRef,
)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _resolve_js_module_path(
    spec: str, current_file: Path, project_root: Path
) -> str:
    """Resolve a JS/TS import specifier to a project-relative path or ``""``.

    Handles ``./``, ``../`` and bare specifiers.  Bare specifiers are treated
    as external and yield ``""``.
    """
    if not spec.startswith("."):
        return ""
    target = (current_file.parent / spec).resolve()
    candidates = [
        target,
        target.with_suffix(".ts"),
        target.with_suffix(".tsx"),
        target.with_suffix(".js"),
        target.with_suffix(".jsx"),
        target.with_suffix(".mjs"),
        target.with_suffix(".cjs"),
        target.with_suffix(".vue"),
        target / "index.ts",
        target / "index.tsx",
        target / "index.js",
        target / "index.jsx",
    ]
    for cand in candidates:
        try:
            if cand.exists() and cand.is_file():
                return cand.resolve().relative_to(project_root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
    return ""


def _collect_imports(
    root: Node, source: bytes, current_file: Path, project_root: Path
) -> Imports:
    external: list[ExternalImport] = []
    internal: list[InternalImport] = []

    def record(spec: str, names: list[str]) -> None:
        target = _resolve_js_module_path(spec, current_file, project_root)
        if target:
            for name in names or [Path(spec).stem]:
                internal.append(
                    InternalImport(
                        name=name,
                        type=resolve_import_type(name),
                        source_path=target,
                    )
                )
        else:
            external.append(ExternalImport(lib=spec, items=list(names)))

    def walk_import(node: Node) -> None:
        # ``import_statement`` shape varies between JS/TS grammar versions;
        # we tolerate both by inspecting children.
        source_node = node.child_by_field_name("source")
        if source_node is None:
            for c in node.named_children:
                if c.type == "string":
                    source_node = c
                    break
        if source_node is None:
            return
        spec = _text(source_node, source).strip().strip("'\"`")
        names: list[str] = []
        for child in node.named_children:
            if child.type == "import_clause":
                names.extend(_names_from_import_clause(child, source))
        record(spec, names)

    for node in _walk(root):
        if node.type == "import_statement":
            walk_import(node)
        elif node.type == "call_expression":
            # ``require('x')`` and dynamic ``import('x')``.
            func = node.child_by_field_name("function")
            if func is None:
                continue
            ftext = _text(func, source).strip()
            args = node.child_by_field_name("arguments")
            if args is None or not args.named_children:
                continue
            first = args.named_children[0]
            if first.type != "string":
                continue
            spec = _text(first, source).strip().strip("'\"`")
            if ftext == "require" or ftext == "import":
                record(spec, [])

    return Imports(external=external, internal=internal)


def _names_from_import_clause(clause: Node, source: bytes) -> list[str]:
    names: list[str] = []
    for child in clause.named_children:
        if child.type == "identifier":
            names.append(_text(child, source))
        elif child.type == "named_imports":
            for spec in child.named_children:
                if spec.type == "import_specifier":
                    name_node = spec.child_by_field_name("name") or (
                        spec.named_children[0] if spec.named_children else None
                    )
                    if name_node is not None:
                        names.append(_text(name_node, source))
        elif child.type == "namespace_import":
            ident = next((c for c in child.named_children if c.type == "identifier"), None)
            if ident is not None:
                names.append(_text(ident, source))
    return names


def _walk(node: Node) -> Iterable[Node]:
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.named_children)


def _walk_calls(body: Node | None) -> Iterable[Node]:
    if body is None:
        return
    stack = list(body.named_children)
    while stack:
        node = stack.pop()
        if node.type == "call_expression":
            yield node
        if node.type in {
            "function_declaration",
            "method_definition",
            "class_declaration",
            "function_expression",
            "arrow_function",
        }:
            continue
        stack.extend(node.named_children)


def _extract_params(params_node: Node | None, source: bytes) -> list[Parameter]:
    if params_node is None:
        return []
    out: list[Parameter] = []
    for child in params_node.named_children:
        t = child.type
        if t in {"identifier", "shorthand_property_identifier_pattern"}:
            out.append(Parameter(name=_text(child, source)))
        elif t == "required_parameter" or t == "optional_parameter":
            ident = child.child_by_field_name("pattern") or next(
                (c for c in child.named_children if c.type == "identifier"), None
            )
            type_anno = child.child_by_field_name("type") or next(
                (c for c in child.named_children if c.type == "type_annotation"), None
            )
            if ident is not None:
                type_text = _text(type_anno, source).lstrip(":").strip() if type_anno else ""
                out.append(Parameter(name=_text(ident, source), type=type_text))
        elif t == "assignment_pattern":
            left = child.child_by_field_name("left") or (
                child.named_children[0] if child.named_children else None
            )
            if left is not None:
                out.append(Parameter(name=_text(left, source)))
    return out


def _extract_return_type(node: Node, source: bytes) -> ReturnSpec:
    rt = node.child_by_field_name("return_type")
    if rt is None:
        return ReturnSpec()
    return ReturnSpec(type=_text(rt, source).lstrip(":").strip())


def _call_name(call: Node, source: bytes) -> str:
    func = call.child_by_field_name("function")
    if func is None:
        return ""
    return _text(func, source).strip()


def _attach_calls_js(
    func: FunctionNode,
    body: Node | None,
    source: bytes,
    file_node: FileNode,
    local_names: set[str],
) -> None:
    seen_int: set[tuple[str, str]] = set()
    seen_ext: set[str] = set()
    for call in _walk_calls(body):
        name = _call_name(call, source)
        if not name:
            continue
        root_name = name.split(".")[0]
        target = ""
        is_internal = False
        if root_name in local_names:
            target = "self"
            is_internal = True
        else:
            for imp in file_node.imports.internal:
                if imp.name == root_name:
                    target = imp.source_path
                    is_internal = True
                    break
        if is_internal:
            key = (name, target)
            if key in seen_int:
                continue
            seen_int.add(key)
            func.calls_internal.append(CallRef(name=name, source_path=target))
        else:
            if name in seen_ext:
                continue
            seen_ext.add(name)
            func.calls_external.append(CallRef(name=name, source_path=""))


def _extract_top_level(
    root: Node, source: bytes, file_node: FileNode
) -> None:
    local_names: set[str] = set()

    # First pass: collect names of top-level declarations.
    for child in root.named_children:
        for name in _decl_names(child, source):
            local_names.add(name)

    for child in root.named_children:
        node = child
        # Unwrap ``export_statement``.
        if node.type == "export_statement":
            inner = node.child_by_field_name("declaration") or next(
                (c for c in node.named_children if c.type != "string"), None
            )
            if inner is None:
                continue
            node = inner

        if node.type in {"class_declaration", "abstract_class_declaration"}:
            _extract_class(node, source, file_node, local_names)
        elif node.type in {"function_declaration", "generator_function_declaration"}:
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _text(name_node, source)
            func = FunctionNode(
                parameters=_extract_params(node.child_by_field_name("parameters"), source),
                returns=_extract_return_type(node, source),
            )
            _attach_calls_js(
                func,
                node.child_by_field_name("body"),
                source,
                file_node,
                local_names,
            )
            file_node.functions[name] = func
        elif node.type in {"lexical_declaration", "variable_declaration"}:
            # ``const foo = () => {}`` / ``const foo = function(){}``
            for declarator in node.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name_node = declarator.child_by_field_name("name")
                value_node = declarator.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                name = _text(name_node, source)
                if value_node.type in {"arrow_function", "function_expression", "function"}:
                    func = FunctionNode(
                        parameters=_extract_params(
                            value_node.child_by_field_name("parameters"), source
                        ),
                        returns=_extract_return_type(value_node, source),
                    )
                    _attach_calls_js(
                        func,
                        value_node.child_by_field_name("body"),
                        source,
                        file_node,
                        local_names,
                    )
                    file_node.functions[name] = func
        elif node.type in {"interface_declaration", "type_alias_declaration"}:
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _text(name_node, source)
            kind = "interface" if node.type == "interface_declaration" else "type_alias"
            file_node.classes[name] = ClassNode(parents=[], decorators=[kind])


def _decl_names(node: Node, source: bytes) -> Iterable[str]:
    inner = node
    if inner.type == "export_statement":
        decl = inner.child_by_field_name("declaration")
        if decl is not None:
            inner = decl
    name_node = inner.child_by_field_name("name") if hasattr(inner, "child_by_field_name") else None
    if name_node is not None:
        yield _text(name_node, source)
    if inner.type in {"lexical_declaration", "variable_declaration"}:
        for declarator in inner.named_children:
            if declarator.type == "variable_declarator":
                n = declarator.child_by_field_name("name")
                if n is not None:
                    yield _text(n, source)


def _extract_class(
    node: Node, source: bytes, file_node: FileNode, local_names: set[str]
) -> None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return
    name = _text(name_node, source)
    parents: list[str] = []
    heritage = node.child_by_field_name("heritage") or next(
        (c for c in node.named_children if c.type == "class_heritage"), None
    )
    if heritage is not None:
        for ch in heritage.named_children:
            txt = _text(ch, source).strip()
            if txt:
                parents.append(txt)
    body = node.child_by_field_name("body")
    methods: dict[str, FunctionNode] = {}
    if body is not None:
        for member in body.named_children:
            if member.type == "method_definition":
                m_name_node = member.child_by_field_name("name")
                if m_name_node is None:
                    continue
                m_name = _text(m_name_node, source)
                func = FunctionNode(
                    parameters=_extract_params(member.child_by_field_name("parameters"), source),
                    returns=_extract_return_type(member, source),
                )
                _attach_calls_js(
                    func,
                    member.child_by_field_name("body"),
                    source,
                    file_node,
                    local_names | {"this"},
                )
                methods[m_name] = func
    file_node.classes[name] = ClassNode(parents=parents, methods=methods)


def _pick_language(lang: str) -> Language:
    if lang == "typescript":
        return typescript_language()
    if lang == "tsx":
        return tsx_language()
    return javascript_language()


def parse_js_like(
    *,
    content: bytes,
    rel_path: str,
    project_root: Path,
    file_hash: str,
    lang: str,
) -> FileNode:
    """Common entry-point used by both the standalone parser and Vue."""
    language = _pick_language("tsx" if rel_path.endswith(".tsx") else lang)
    parser = make_parser(language)
    tree = parser.parse(content)
    root = tree.root_node
    current_file = (project_root / rel_path).resolve()

    meta = FileMeta(lang=lang, hash=file_hash, path=rel_path)
    imports = _collect_imports(root, content, current_file, project_root)
    file_node = FileNode(_meta=meta, imports=imports)
    _extract_top_level(root, content, file_node)
    return file_node


class JavaScriptParser:
    lang = "javascript"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        return parse_js_like(
            content=content,
            rel_path=rel_path,
            project_root=project_root,
            file_hash=file_hash,
            lang="javascript",
        )


class TypeScriptParser:
    lang = "typescript"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        return parse_js_like(
            content=content,
            rel_path=rel_path,
            project_root=project_root,
            file_hash=file_hash,
            lang="typescript",
        )
