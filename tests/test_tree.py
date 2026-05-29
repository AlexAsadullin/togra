from togra.graph.tree import insert_into_tree


def test_creates_directories():
    g: dict = {}
    insert_into_tree(g, "src/auth/login.py", {"_meta": {"type": "file"}, "description": ""})
    assert g["project_root"]["src"]["auth"]["login.py"]["_meta"]["type"] == "file"
    assert g["project_root"]["src"]["_meta"]["type"] == "directory"
    assert g["project_root"]["src"]["auth"]["_meta"]["path"] == "src/auth"


def test_multiple_files():
    g: dict = {}
    insert_into_tree(g, "a.py", {"_meta": {"type": "file"}})
    insert_into_tree(g, "src/b.py", {"_meta": {"type": "file"}})
    assert "a.py" in g["project_root"]
    assert "b.py" in g["project_root"]["src"]
