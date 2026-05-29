"""Python parser built on top of ``tree-sitter-python``.

Maps Python AST nodes onto the togra schema as described in tech-task §4
and §6.4.  Highlights:

* ``import_statement`` / ``import_from_statement`` → :class:`Imports`;
* ``class_definition`` (incl. ``decorated_definition`` wrappers) → :class:`ClassNode`;
* ``function_definition`` / ``async_function_definition`` → :class:`FunctionNode`;
* Method calls and bare ``call`` nodes → ``calls_internal`` / ``calls_external``.

The parser is pure (no I/O beyond the supplied bytes; uses
:func:`togra.resolve.imports.resolve_relative_path` to map dotted imports
to files inside the project).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from tree_sitter import Node

from togra.parsers._ts_loader import make_parser, python_language
from togra.resolve.imports import resolve_import_type, resolve_relative_path
from togra.schema import (
    Attribute,
    CallRef,
    ClassNode,
    ExternalImport,
    FileMeta,
    FileNode,
    FunctionNode,
    Imports,
    InternalImport,
    Parameter,
    ReturnSpec,
)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _children_by_type(node: Node, types: Iterable[str]) -> list[Node]:
    wanted = set(types)
    return [c for c in node.named_children if c.type in wanted]


def _identifier_text(node: Node, source: bytes) -> str:
    """For ``identifier`` / ``dotted_name`` nodes return their textual form."""
    return _text(node, source).strip()


# --- imports ----------------------------------------------------------------


def _extract_module_name(node: Node, source: bytes) -> tuple[str, int]:
    """Return ``(module_text, leading_dots)`` for an ``import_from`` module.

    ``node`` is either ``dotted_name`` or ``relative_import``.  The leading
    dot count lets :func:`resolve_relative_path` walk parents correctly.
    """
    if node.type == "dotted_name":
        return _identifier_text(node, source), 0
    if node.type == "relative_import":
        prefix_node = node.child_by_field_name("prefix")
        dotted = node.child_by_field_name("module_name") or next(
            (c for c in node.named_children if c.type == "dotted_name"), None
        )
        # ``prefix`` may not be exposed as a field on every grammar release;
        # fall back to counting leading dots in the raw text.
        text = _text(node, source)
        leading_dots = 0
        for ch in text:
            if ch == ".":
                leading_dots += 1
            else:
                break
        name = _identifier_text(dotted, source) if dotted is not None else ""
        del prefix_node  # silence unused warning
        return name, leading_dots
    return _identifier_text(node, source), 0


def _name_from_aliased(node: Node, source: bytes) -> str:
    """``aliased_import`` → original name (we ignore the alias for graph purposes)."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        for child in node.named_children:
            if child.type in {"dotted_name", "identifier"}:
                name_node = child
                break
    return _identifier_text(name_node, source) if name_node is not None else ""


def _collect_imports(
    root: Node, source: bytes, current_file: Path, project_root: Path
) -> Imports:
    external: list[ExternalImport] = []
    internal: list[InternalImport] = []

    def handle_import_statement(node: Node) -> None:
        # `import a, b as c`
        for child in node.named_children:
            if child.type == "dotted_name":
                module = _identifier_text(child, source)
                _record_module(module, [], leading_dots=0)
            elif child.type == "aliased_import":
                inner = child.child_by_field_name("name") or next(
                    (c for c in child.named_children if c.type in {"dotted_name", "identifier"}),
                    None,
                )
                if inner is not None:
                    module = _identifier_text(inner, source)
                    _record_module(module, [], leading_dots=0)

    def handle_from_import(node: Node) -> None:
        module_node = node.child_by_field_name("module_name")
        if module_node is None:
            return
        module, leading_dots = _extract_module_name(module_node, source)
        names: list[str] = []
        # tree-sitter returns fresh Node wrappers from child_by_field_name,
        # so `is` doesn't match — compare byte offsets instead.
        module_span = (module_node.start_byte, module_node.end_byte)
        for child in node.named_children:
            if (child.start_byte, child.end_byte) == module_span:
                continue
            if child.type == "dotted_name":
                names.append(_identifier_text(child, source))
            elif child.type == "aliased_import":
                names.append(_name_from_aliased(child, source))
            elif child.type == "wildcard_import":
                names.append("*")
        _record_module(module, names, leading_dots=leading_dots)

    def _record_module(module: str, names: list[str], leading_dots: int) -> None:
        # Decide internal vs external.
        if leading_dots > 0:
            dotted = "." * leading_dots + module
            resolved = resolve_relative_path(dotted, current_file, project_root)
            target = resolved if resolved != dotted else ""
            is_internal = bool(target)
        else:
            resolved = resolve_relative_path(module, current_file, project_root)
            is_internal = resolved != module
            target = resolved if is_internal else ""

        if is_internal:
            if names:
                for name in names:
                    internal.append(
                        InternalImport(
                            name=name,
                            type=resolve_import_type(name),
                            source_path=target,
                        )
                    )
            else:
                # ``import pkg`` of an internal package — record the module
                # itself so consumers still see the edge.
                internal.append(
                    InternalImport(
                        name=module.split(".")[-1] or module,
                        type="module",
                        source_path=target,
                    )
                )
        else:
            external.append(ExternalImport(lib=module, items=list(names)))

    for child in root.named_children:
        if child.type == "import_statement":
            handle_import_statement(child)
        elif child.type == "import_from_statement":
            handle_from_import(child)

    return Imports(external=external, internal=internal)


# --- functions / methods ----------------------------------------------------


def _extract_parameters(params_node: Node | None, source: bytes) -> list[Parameter]:
    if params_node is None:
        return []
    out: list[Parameter] = []
    for child in params_node.named_children:
        t = child.type
        if t == "identifier":
            out.append(Parameter(name=_identifier_text(child, source)))
        elif t == "typed_parameter":
            ident = next((c for c in child.named_children if c.type == "identifier"), None)
            type_node = next((c for c in child.named_children if c.type == "type"), None)
            if ident is not None:
                out.append(
                    Parameter(
                        name=_identifier_text(ident, source),
                        type=_identifier_text(type_node, source) if type_node else "",
                    )
                )
        elif t == "default_parameter":
            name_node = child.child_by_field_name("name") or next(
                (c for c in child.named_children if c.type == "identifier"), None
            )
            if name_node is not None:
                out.append(Parameter(name=_identifier_text(name_node, source)))
        elif t == "typed_default_parameter":
            name_node = child.child_by_field_name("name") or next(
                (c for c in child.named_children if c.type == "identifier"), None
            )
            type_node = child.child_by_field_name("type") or next(
                (c for c in child.named_children if c.type == "type"), None
            )
            if name_node is not None:
                out.append(
                    Parameter(
                        name=_identifier_text(name_node, source),
                        type=_identifier_text(type_node, source) if type_node else "",
                    )
                )
        elif t in {"list_splat_pattern", "dictionary_splat_pattern"}:
            out.append(Parameter(name=_text(child, source).strip()))
    return out


def _extract_return(func_node: Node, source: bytes) -> ReturnSpec:
    rt = func_node.child_by_field_name("return_type")
    if rt is None:
        return ReturnSpec()
    return ReturnSpec(type=_identifier_text(rt, source))


def _extract_decorators(decorated_node: Node, source: bytes) -> list[str]:
    """``decorated_definition`` lists ``decorator`` children before the def."""
    out: list[str] = []
    for child in decorated_node.named_children:
        if child.type != "decorator":
            continue
        # ``decorator`` has one expression child after the ``@``.  Take text.
        text = _text(child, source).strip()
        out.append(text)
    return out


def _call_name(call_node: Node, source: bytes) -> str:
    func = call_node.child_by_field_name("function")
    if func is None:
        return ""
    if func.type == "identifier":
        return _identifier_text(func, source)
    if func.type == "attribute":
        # ``a.b.c`` — return the dotted text.
        return _text(func, source).strip()
    return _text(func, source).strip()


def _walk_calls(body: Node | None) -> Iterable[Node]:
    if body is None:
        return
    stack = list(body.named_children)
    while stack:
        node = stack.pop()
        if node.type == "call":
            yield node
        # Recurse, but skip nested function/class so we attribute calls to
        # the enclosing definition only.
        if node.type in {"function_definition", "async_function_definition", "class_definition"}:
            continue
        stack.extend(node.named_children)


def _resolve_call(
    call_name: str,
    file_node: FileNode,
    local_funcs: set[str],
    local_classes: set[str],
) -> CallRef | tuple[CallRef, bool]:
    """Return ``(CallRef, is_internal)``.

    * Calls whose root identifier matches a function/class defined in the
      same file get ``source_path="self"``.
    * Calls whose root identifier matches an internal import inherit that
      import's ``source_path``.
    * Otherwise ``source_path=""`` and the call is classified external.
    """
    root_name = call_name.split(".")[0] if call_name else ""
    if root_name in local_funcs or root_name in local_classes:
        return CallRef(name=call_name, source_path="self"), True
    for imp in file_node.imports.internal:
        if imp.name == root_name:
            return CallRef(name=call_name, source_path=imp.source_path), True
    return CallRef(name=call_name, source_path=""), False


def _extract_function(
    func_node: Node,
    source: bytes,
    decorators: list[str],
) -> FunctionNode:
    params_node = func_node.child_by_field_name("parameters")
    body_node = func_node.child_by_field_name("body")
    return FunctionNode(
        decorators=decorators,
        parameters=_extract_parameters(params_node, source),
        returns=_extract_return(func_node, source),
        # calls are attached in a second pass once we know local names.
    )


def _attach_calls(
    func: FunctionNode,
    body_node: Node | None,
    source: bytes,
    file_node: FileNode,
    local_funcs: set[str],
    local_classes: set[str],
) -> None:
    seen_internal: set[tuple[str, str]] = set()
    seen_external: set[str] = set()
    for call in _walk_calls(body_node):
        name = _call_name(call, source)
        if not name:
            continue
        ref, is_internal = _resolve_call(name, file_node, local_funcs, local_classes)
        if is_internal:
            key = (ref.name, ref.source_path)
            if key in seen_internal:
                continue
            seen_internal.add(key)
            func.calls_internal.append(ref)
        else:
            if name in seen_external:
                continue
            seen_external.add(name)
            func.calls_external.append(ref)


def _extract_class_body(
    body_node: Node | None,
    source: bytes,
) -> tuple[list[Attribute], dict[str, FunctionNode], dict[str, Node]]:
    """Return (attributes, methods, method_body_index)."""
    attributes: list[Attribute] = []
    methods: dict[str, FunctionNode] = {}
    method_bodies: dict[str, Node] = {}
    if body_node is None:
        return attributes, methods, method_bodies

    for stmt in body_node.named_children:
        # Class-level attributes: ``x: T = ...`` or ``x = ...``.
        if stmt.type == "expression_statement":
            inner = stmt.named_children[0] if stmt.named_children else None
            if inner and inner.type == "assignment":
                left = inner.child_by_field_name("left") or (
                    inner.named_children[0] if inner.named_children else None
                )
                if left is not None and left.type == "identifier":
                    type_node = inner.child_by_field_name("type")
                    attributes.append(
                        Attribute(
                            name=_identifier_text(left, source),
                            type=_identifier_text(type_node, source) if type_node else "",
                        )
                    )
            continue

        # Plain or decorated method.
        decorators: list[str] = []
        method_node: Node | None = None
        if stmt.type in {"function_definition", "async_function_definition"}:
            method_node = stmt
        elif stmt.type == "decorated_definition":
            decorators = _extract_decorators(stmt, source)
            method_node = stmt.child_by_field_name("definition") or next(
                (
                    c
                    for c in stmt.named_children
                    if c.type in {"function_definition", "async_function_definition"}
                ),
                None,
            )

        if method_node is None:
            continue
        name_node = method_node.child_by_field_name("name")
        if name_node is None:
            continue
        method_name = _identifier_text(name_node, source)
        func = _extract_function(method_node, source, decorators)
        methods[method_name] = func
        body = method_node.child_by_field_name("body")
        if body is not None:
            method_bodies[method_name] = body

            # Harvest ``self.x = ...`` attributes from __init__.
            if method_name == "__init__":
                for sub in _iter_self_assignments(body, source):
                    attributes.append(sub)

    # Deduplicate attributes by name preserving order, prefer typed entries.
    dedup: dict[str, Attribute] = {}
    for attr in attributes:
        existing = dedup.get(attr.name)
        if existing is None or (not existing.type and attr.type):
            dedup[attr.name] = attr
    return list(dedup.values()), methods, method_bodies


def _iter_self_assignments(body: Node, source: bytes) -> Iterable[Attribute]:
    """Yield ``Attribute`` for every ``self.<name>[: T] = ...`` in ``body``."""
    stack = list(body.named_children)
    while stack:
        node = stack.pop()
        if node.type in {"function_definition", "async_function_definition", "class_definition"}:
            continue
        if node.type == "expression_statement" and node.named_children:
            inner = node.named_children[0]
            if inner.type == "assignment":
                left = inner.child_by_field_name("left") or (
                    inner.named_children[0] if inner.named_children else None
                )
                if left is not None and left.type == "attribute":
                    object_node = left.child_by_field_name("object")
                    attr_node = left.child_by_field_name("attribute")
                    if (
                        object_node is not None
                        and attr_node is not None
                        and _identifier_text(object_node, source) == "self"
                    ):
                        type_node = inner.child_by_field_name("type")
                        yield Attribute(
                            name=_identifier_text(attr_node, source),
                            type=_identifier_text(type_node, source) if type_node else "",
                        )
        stack.extend(node.named_children)


# --- top-level extraction ---------------------------------------------------


def _iter_top_level_defs(root: Node) -> Iterable[tuple[Node, list[Node]]]:
    """Yield ``(definition_node, decorator_nodes)`` for top-level defs."""
    for child in root.named_children:
        if child.type in {
            "function_definition",
            "async_function_definition",
            "class_definition",
        }:
            yield child, []
        elif child.type == "decorated_definition":
            decorators = [c for c in child.named_children if c.type == "decorator"]
            inner = child.child_by_field_name("definition") or next(
                (
                    c
                    for c in child.named_children
                    if c.type
                    in {
                        "function_definition",
                        "async_function_definition",
                        "class_definition",
                    }
                ),
                None,
            )
            if inner is not None:
                yield inner, decorators


def _decorator_text(decorators: list[Node], source: bytes) -> list[str]:
    return [_text(d, source).strip() for d in decorators]


class PythonParser:
    lang = "python"

    def parse(
        self,
        *,
        content: bytes,
        rel_path: str,
        project_root: Path,
        file_hash: str,
    ) -> FileNode:
        parser = make_parser(python_language())
        tree = parser.parse(content)
        root = tree.root_node
        current_file = (project_root / rel_path).resolve()

        meta = FileMeta(lang="python", hash=file_hash, path=rel_path)
        imports = _collect_imports(root, content, current_file, project_root)

        file_node = FileNode(_meta=meta, imports=imports)

        # First pass: classify all top-level defs into classes/functions so
        # we know which names are "local" before resolving calls.
        top_classes: dict[str, tuple[Node, list[str], Node | None]] = {}
        top_functions: dict[str, tuple[Node, list[str], Node | None]] = {}

        for def_node, decorators_nodes in _iter_top_level_defs(root):
            decorator_strs = _decorator_text(decorators_nodes, content)
            name_node = def_node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _identifier_text(name_node, content)
            body_node = def_node.child_by_field_name("body")
            if def_node.type == "class_definition":
                top_classes[name] = (def_node, decorator_strs, body_node)
            else:
                top_functions[name] = (def_node, decorator_strs, body_node)

        local_funcs = set(top_functions.keys())
        local_classes = set(top_classes.keys())

        # Build classes (with their methods) and functions.
        for cname, (cnode, cdecs, cbody) in top_classes.items():
            parents: list[str] = []
            superclasses = cnode.child_by_field_name("superclasses")
            if superclasses is not None:
                for arg in superclasses.named_children:
                    parents.append(_text(arg, content).strip())
            attributes, methods, method_bodies = _extract_class_body(cbody, content)
            class_node = ClassNode(
                parents=parents,
                decorators=cdecs,
                attributes=attributes,
                methods=methods,
            )
            file_node.classes[cname] = class_node
            # Attach calls per method (deferred until file_node imports are set).
            for mname, mfunc in methods.items():
                _attach_calls(
                    mfunc,
                    method_bodies.get(mname),
                    content,
                    file_node,
                    local_funcs | {"self"},
                    local_classes,
                )

        for fname, (fnode, fdecs, fbody) in top_functions.items():
            func = _extract_function(fnode, content, fdecs)
            _attach_calls(func, fbody, content, file_node, local_funcs, local_classes)
            file_node.functions[fname] = func

        return file_node
