from pathlib import Path

from togra.cache.diff import diff_files


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_new_files_are_dirty(tmp_path: Path):
    a = tmp_path / "a.py"
    write(a, "x = 1")
    result = diff_files([a], tmp_path, index={}, mode="update")
    assert "a.py" in result.dirty
    assert "a.py" in result.new


def test_unchanged_file_is_clean(tmp_path: Path):
    a = tmp_path / "a.py"
    write(a, "x = 1")
    from togra.fs.hashing import compute_file_hash

    index = {"a.py": {"hash": compute_file_hash(a), "lang": "python", "fragment": "h.json"}}
    result = diff_files([a], tmp_path, index, mode="update")
    assert "a.py" in result.clean
    assert "a.py" not in result.dirty


def test_modified_file_dirty_in_update_mode(tmp_path: Path):
    a = tmp_path / "a.py"
    write(a, "x = 1")
    index = {"a.py": {"hash": "stale", "lang": "python", "fragment": "old.json"}}
    result = diff_files([a], tmp_path, index, mode="update")
    assert "a.py" in result.dirty


def test_newonly_keeps_modified_clean(tmp_path: Path):
    a = tmp_path / "a.py"
    write(a, "y = 2")
    index = {"a.py": {"hash": "stale", "lang": "python", "fragment": "old.json"}}
    result = diff_files([a], tmp_path, index, mode="newonly")
    assert "a.py" in result.clean
    assert "a.py" not in result.dirty


def test_full_mode_marks_everything_dirty(tmp_path: Path):
    a = tmp_path / "a.py"
    write(a, "x = 1")
    from togra.fs.hashing import compute_file_hash

    index = {"a.py": {"hash": compute_file_hash(a), "lang": "python", "fragment": "h.json"}}
    result = diff_files([a], tmp_path, index, mode="full")
    assert "a.py" in result.dirty


def test_removed_entries(tmp_path: Path):
    index = {"gone.py": {"hash": "h", "lang": "python", "fragment": "h.json"}}
    result = diff_files([], tmp_path, index, mode="update")
    assert "gone.py" in result.removed
