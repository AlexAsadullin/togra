"""End-to-end CLI tests against a synthetic project."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from togra.cli import app
from togra.schema import assert_descriptions_empty


runner = CliRunner()


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    for sub in ("src/auth", "src/models", "src/utils", "src/config"):
        (tmp_path / sub).mkdir(parents=True)
        (tmp_path / sub / "__init__.py").touch()
    (tmp_path / "src/__init__.py").touch()
    (tmp_path / "src/auth/login.py").write_text(
        "from ..models.user import User\n"
        "from ..utils.crypto import hash_password\n\n"
        "class AuthService:\n"
        "    def go(self):\n"
        "        return User.get()\n"
    )
    (tmp_path / "src/models/user.py").write_text(
        "class User:\n    @classmethod\n    def get(cls):\n        return None\n"
    )
    (tmp_path / "src/utils/crypto.py").write_text(
        "def hash_password(p):\n    return p\n"
    )
    (tmp_path / "src/config/settings.py").write_text("APP_CONFIG = {}\n")
    return tmp_path


def _invoke(args: list[str]) -> None:
    result = runner.invoke(app, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_init_then_build_and_descriptions_empty(py_project: Path):
    _invoke(["init", "--project", str(py_project)])
    _invoke(["build", "--project", str(py_project)])

    graph_path = py_project / "togra-output" / "graph.json"
    assert graph_path.exists()
    graph = json.loads(graph_path.read_text())
    assert_descriptions_empty(graph)

    login = graph["project_root"]["src"]["auth"]["login.py"]
    assert "AuthService" in login["classes"]
    assert login["_meta"]["lang"] == "python"


def test_incremental_only_dirty_reparsed(py_project: Path):
    _invoke(["init", "--project", str(py_project)])
    _invoke(["build", "--project", str(py_project)])

    manifest = json.loads(
        (py_project / "togra-output" / "manifest.json").read_text()
    )
    # All files were initially dirty.
    first_dirty = manifest["stats"]["dirty"]
    assert first_dirty > 0

    # No changes → no dirty.
    _invoke(["build", "--project", str(py_project)])
    manifest = json.loads(
        (py_project / "togra-output" / "manifest.json").read_text()
    )
    assert manifest["stats"]["dirty"] == 0

    # Touch one file's content.
    target = py_project / "src/utils/crypto.py"
    target.write_text(target.read_text() + "\n# noop\n")
    _invoke(["build", "--project", str(py_project)])
    manifest = json.loads(
        (py_project / "togra-output" / "manifest.json").read_text()
    )
    assert manifest["stats"]["dirty"] == 1


def test_lang_filter(py_project: Path):
    _invoke(["init", "--project", str(py_project)])
    (py_project / "extra.json").write_text('{"a": 1}')
    _invoke(["build", "--project", str(py_project), "--lang", "python"])
    graph = json.loads(
        (py_project / "togra-output" / "graph.json").read_text()
    )
    # JSON file must be excluded under --lang python.
    assert "extra.json" not in graph["project_root"]


def test_clean(py_project: Path):
    _invoke(["init", "--project", str(py_project)])
    _invoke(["build", "--project", str(py_project)])
    _invoke(["clean", "--project", str(py_project)])
    fragments_dir = py_project / "togra-output" / "cache" / "fragments"
    # `clean` recreates the empty layout.
    assert fragments_dir.exists()
    assert list(fragments_dir.iterdir()) == []


def test_clean_all(py_project: Path):
    _invoke(["init", "--project", str(py_project)])
    _invoke(["clean", "--project", str(py_project), "--all"])
    assert not (py_project / "togra-output").exists()


def test_init_copies_gitignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("custom-marker\n")
    _invoke(["init", "--project", str(tmp_path)])
    assert "custom-marker" in (tmp_path / ".tograignore").read_text()


def test_init_writes_agent_guide(tmp_path: Path):
    _invoke(["init", "--project", str(tmp_path)])
    guide = tmp_path / "AGENT_GUIDE.md"
    assert guide.exists()
    text = guide.read_text(encoding="utf-8")
    # Sanity: must contain the canonical heading shipped in the template.
    assert "Guide for the description-filling agent" in text


def test_init_does_not_overwrite_agent_guide(tmp_path: Path):
    guide = tmp_path / "AGENT_GUIDE.md"
    guide.write_text("my custom guide\n", encoding="utf-8")
    _invoke(["init", "--project", str(tmp_path)])
    assert guide.read_text(encoding="utf-8") == "my custom guide\n"
