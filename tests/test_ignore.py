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
