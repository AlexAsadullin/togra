import json
from pathlib import Path

import pytest

from togra.fs.atomic import atomic_write_json


def test_writes_json(tmp_path: Path):
    target = tmp_path / "out" / "graph.json"
    atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text()) == {"a": 1}


def test_no_temp_files_left(tmp_path: Path):
    target = tmp_path / "graph.json"
    atomic_write_json(target, {"x": [1, 2]})
    leftovers = [p for p in tmp_path.iterdir() if p.name != "graph.json"]
    assert leftovers == []


def test_failure_cleans_tmp(tmp_path: Path):
    target = tmp_path / "graph.json"

    class _Bad:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"x": _Bad()})  # not JSON serialisable
    # Target was never created and tmp file was removed.
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
