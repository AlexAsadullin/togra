from pathlib import Path

from togra.parsers.css_parser import CssParser
from togra.parsers.fallback import FallbackParser
from togra.parsers.html_parser import HtmlParser
from togra.parsers.json_parser import JsonParser


def test_css(tmp_path: Path):
    content = b"""
    @import url('reset.css');
    .btn, #main { color: red; background: url(/img.png); }
    @media (min-width: 600px) { .btn { color: blue; } }
    """
    node = CssParser().parse(content=content, rel_path="style.css", project_root=tmp_path, file_hash="h")
    assert "selectors" in node.extras
    assert ".btn" in node.extras["selectors"]
    assert "#main" in node.extras["selectors"]
    assert node.extras.get("imports_css") == ["reset.css"]
    assert "/img.png" in node.extras.get("urls", [])
    assert any("min-width" in q for q in node.extras.get("media_queries", []))


def test_html(tmp_path: Path):
    html = b"""
    <html><body>
    <div id="root" class="main wide">
        <script src="app.js"></script>
        <link href="style.css" rel="stylesheet"/>
        <p>hello</p>
    </div></body></html>
    """
    node = HtmlParser().parse(content=html, rel_path="index.html", project_root=tmp_path, file_hash="h")
    assert "div" in node.extras["tags"]
    assert "main" in node.extras["classes"]
    assert "root" in node.extras["ids"]
    assert "app.js" in node.extras["scripts"]
    assert "style.css" in node.extras["links"]


def test_json(tmp_path: Path):
    content = b'{"name": "x", "deps": ["a", "b"], "n": 1}'
    node = JsonParser().parse(content=content, rel_path="pkg.json", project_root=tmp_path, file_hash="h")
    tree = node.extras["keys_tree"]
    assert tree["name"] == "str"
    assert tree["n"] == "int"
    assert tree["deps"] == ["str"]


def test_json_invalid(tmp_path: Path):
    node = JsonParser().parse(content=b"{bad", rel_path="p.json", project_root=tmp_path, file_hash="h")
    assert node.extras["keys_tree"] is None
    assert "parse_error" in node.extras


def test_fallback(tmp_path: Path):
    node = FallbackParser().parse(
        content=b"opaque", rel_path="weird.rs", project_root=tmp_path, file_hash="h"
    )
    assert node.meta.lang == "unknown"
    assert node.meta.path == "weird.rs"
    assert node.description == ""
    assert node.classes == {}
    assert node.functions == {}
