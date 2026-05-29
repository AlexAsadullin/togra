"""Pydantic models that describe the on-disk graph schema.

The graph itself is represented as a nested ``dict`` mirroring the project's
directory tree (see tech-task.md §5).  The leaf nodes are :class:`FileNode`
instances serialised through :meth:`pydantic.BaseModel.model_dump`.

Invariants enforced by the schema:

* All ``description`` fields default to ``""`` and are never populated by
  ``togra`` itself.
* Numeric / string fields are typed strictly so that downstream consumers
  (AI agents) get a predictable shape.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- imports ----------------------------------------------------------------


class ExternalImport(_Base):
    lib: str
    items: list[str] = Field(default_factory=list)


class InternalImport(_Base):
    name: str
    # "class" / "function" / "constant" / "unknown" — kept as free-form str to
    # avoid blocking future language additions.
    type: str
    source_path: str


class Imports(_Base):
    external: list[ExternalImport] = Field(default_factory=list)
    internal: list[InternalImport] = Field(default_factory=list)


# --- attributes / parameters / calls ----------------------------------------


class Attribute(_Base):
    name: str
    type: str = ""


class Parameter(_Base):
    name: str
    type: str = ""


class ReturnSpec(_Base):
    type: str = ""


class CallRef(_Base):
    name: str
    source_path: str  # "self" for in-file calls, relative path otherwise


# --- functions / methods / classes ------------------------------------------


class FunctionNode(_Base):
    description: str = ""
    decorators: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    returns: ReturnSpec = Field(default_factory=ReturnSpec)
    calls_internal: list[CallRef] = Field(default_factory=list)
    calls_external: list[CallRef] = Field(default_factory=list)


class ClassNode(_Base):
    description: str = ""
    parents: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)
    attributes: list[Attribute] = Field(default_factory=list)
    methods: dict[str, FunctionNode] = Field(default_factory=dict)


# --- file meta --------------------------------------------------------------


class FileMeta(_Base):
    type: Literal["file"] = "file"
    lang: str
    hash: str
    path: str
    tags: list[str] = Field(default_factory=list)
    last_updated: str = ""


class DirMeta(_Base):
    type: Literal["directory"] = "directory"
    path: str = ""


# --- file node --------------------------------------------------------------


class FileNode(_Base):
    """Common envelope.  Specific parsers populate only the fields they know.

    The ``extras`` dict is used by simplified parsers (CSS/HTML/JSON) to
    expose format-specific metadata (selectors, tags, keys_tree) without
    polluting the strict schema for code files.
    """

    meta: FileMeta = Field(alias="_meta")
    description: str = ""
    imports: Imports = Field(default_factory=Imports)
    classes: dict[str, ClassNode] = Field(default_factory=dict)
    functions: dict[str, FunctionNode] = Field(default_factory=dict)
    # Free-form bag for simplified parsers; e.g. {"selectors": [...]}.
    extras: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_fragment(self) -> dict[str, Any]:
        """Serialise to the on-disk fragment shape used by the graph tree.

        The ``extras`` keys are merged into the top level so the JSON matches
        the schema described in tech-task §5 (e.g. ``selectors`` appears
        directly on the file node, not nested under ``extras``).
        """
        data = self.model_dump(by_alias=True, mode="json", exclude={"extras"})
        for key, value in self.extras.items():
            data[key] = value
        return data


def assert_descriptions_empty(node: Any, path: str = "") -> None:
    """Recursively assert that every ``description`` field is the empty string.

    Used as a safety net in tests and at the end of ``togra build`` so we
    never accidentally smuggle generated prose into the graph.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            # ``description`` is a schema field only when its value is a
            # string.  When the dict is a ``methods``/``functions``/``classes``
            # map, the key ``"description"`` is just the entity's name and
            # the value is its (nested) node — recurse into it instead of
            # comparing to "".
            if key == "description" and isinstance(value, str):
                if value != "":
                    raise AssertionError(
                        f"Non-empty description at {path or '<root>'}: {value!r}"
                    )
            else:
                assert_descriptions_empty(value, f"{path}/{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            assert_descriptions_empty(item, f"{path}[{i}]")
