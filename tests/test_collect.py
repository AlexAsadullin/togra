from pathlib import Path

from togra.fs.collect import collect_files
from togra.ignore import IgnoreMatcher


def _touch(p: Path, content: str = "") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_collects_files_and_filters_by_extension(tmp_project: Path):
    _touch(tmp_project / "a.py", "x = 1")
    _touch(tmp_project / "b.txt", "ignore me")
    files = collect_files(tmp_project, IgnoreMatcher.empty(), extensions={".py"})
    assert {f.name for f in files} == {"a.py"}


def test_excludes_togra_output(tmp_project: Path):
    _touch(tmp_project / "a.py")
    _touch(tmp_project / "togra-output" / "graph.json", "{}")
    _touch(tmp_project / "togra-output" / "cache" / "fragments" / "x.json", "{}")
    files = collect_files(tmp_project, IgnoreMatcher.empty(), extensions={".py", ".json"})
    names = {f.relative_to(tmp_project).as_posix() for f in files}
    assert names == {"a.py"}


def test_respects_ignore(tmp_project: Path):
    _touch(tmp_project / "keep.py")
    _touch(tmp_project / "node_modules" / "x.js")
    matcher = IgnoreMatcher.from_text("node_modules/\n")
    files = collect_files(tmp_project, matcher, extensions={".py", ".js"})
    assert {f.relative_to(tmp_project).as_posix() for f in files} == {"keep.py"}
