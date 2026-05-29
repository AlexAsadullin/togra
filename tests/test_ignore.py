from togra.ignore import IgnoreMatcher


def test_blank_and_comment():
    m = IgnoreMatcher.from_text("# comment\n\n")
    assert not m.matches("a.py")


def test_simple_extension():
    m = IgnoreMatcher.from_text("*.pyc\n")
    assert m.matches("a.pyc")
    assert m.matches("pkg/sub/b.pyc")
    assert not m.matches("a.py")


def test_directory_pattern():
    m = IgnoreMatcher.from_text("node_modules/\n")
    assert m.matches("node_modules/x/y.js")
    assert m.matches("a/node_modules/x.js")


def test_anchored_pattern():
    m = IgnoreMatcher.from_text("/build/\n")
    assert m.matches("build/x.txt")
    assert not m.matches("src/build/x.txt")


def test_negation():
    m = IgnoreMatcher.from_text("*.log\n!keep.log\n")
    assert m.matches("a.log")
    assert not m.matches("keep.log")


def test_double_star():
    m = IgnoreMatcher.from_text("**/dist/**\n")
    assert m.matches("dist/x.js")
    assert m.matches("pkg/dist/sub/y.js")


def test_path_pattern_without_trailing_slash_ignores_contents():
    """`backend/uv_venv` (no trailing /) must ignore files inside it,
    matching git's behaviour.
    """
    m = IgnoreMatcher.from_text("backend/uv_venv\n")
    assert m.matches("backend/uv_venv")
    assert m.matches("backend/uv_venv/lib/python3.13/site-packages/aiohttp/x.py")
    assert not m.matches("backend/other.py")


def test_anchored_subdir_pattern_without_slash():
    m = IgnoreMatcher.from_text("frontend/dist\n")
    assert m.matches("frontend/dist/index.html")
    assert m.matches("frontend/dist/assets/app.js")
    assert not m.matches("frontend/src/main.ts")
