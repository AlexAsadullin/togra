from pathlib import Path

from togra.parsers.python_parser import PythonParser


SOURCE = b"""
from fastapi import APIRouter, Depends
from ..models.user import User
from ..utils.crypto import hash_password
from ..config.settings import APP_CONFIG

@singleton
class AuthService(BaseService):
    def __init__(self):
        self.db_session: Session = None
        self.cache: RedisClient = None

    @retry
    def authenticate(self, username: str, password: str) -> AuthResult:
        self.validate_input(username)
        return User.get_by_name(username)

def get_current_user(token: str) -> User:
    return User.get(token)
"""


def _scaffold(root: Path) -> None:
    for sub in ("auth", "models", "utils", "config"):
        (root / "src" / sub).mkdir(parents=True, exist_ok=True)
        (root / "src" / sub / "__init__.py").touch()
    (root / "src/__init__.py").touch()
    (root / "src/models/user.py").write_text("class User: pass\n")
    (root / "src/utils/crypto.py").write_text("def hash_password(p): ...\n")
    (root / "src/config/settings.py").write_text("APP_CONFIG = {}\n")


def test_parses_imports_classes_functions(tmp_path: Path):
    _scaffold(tmp_path)
    target = tmp_path / "src/auth/login.py"
    target.write_bytes(SOURCE)

    parser = PythonParser()
    node = parser.parse(
        content=SOURCE,
        rel_path="src/auth/login.py",
        project_root=tmp_path,
        file_hash="h",
    )

    # Imports
    libs = {i.lib for i in node.imports.external}
    assert "fastapi" in libs
    internal_by_name = {i.name: i for i in node.imports.internal}
    assert internal_by_name["User"].source_path == "src/models/user.py"
    assert internal_by_name["User"].type == "class"
    assert internal_by_name["hash_password"].source_path == "src/utils/crypto.py"
    assert internal_by_name["hash_password"].type == "function"
    assert internal_by_name["APP_CONFIG"].type == "constant"

    # Class + decorators + parents + attributes
    cls = node.classes["AuthService"]
    assert cls.parents == ["BaseService"]
    assert cls.decorators == ["@singleton"]
    attr_names = {a.name: a.type for a in cls.attributes}
    assert attr_names.get("db_session") == "Session"
    assert attr_names.get("cache") == "RedisClient"

    # Method authenticate
    auth = cls.methods["authenticate"]
    assert auth.decorators == ["@retry"]
    assert {p.name: p.type for p in auth.parameters} == {
        "self": "",
        "username": "str",
        "password": "str",
    }
    assert auth.returns.type == "AuthResult"
    internal_calls = {(c.name, c.source_path) for c in auth.calls_internal}
    assert ("self.validate_input", "self") in internal_calls
    assert ("User.get_by_name", "src/models/user.py") in internal_calls

    # Top-level function
    fn = node.functions["get_current_user"]
    assert fn.parameters[0].name == "token"
    assert fn.returns.type == "User"


def test_method_named_description_does_not_break_invariant(tmp_path: Path):
    """A class with a method literally called ``description`` must not
    confuse the safety check — the value at ``methods.description`` is a
    FunctionNode, not the file's description string.
    """
    src = (
        b"class Box:\n"
        b"    @property\n"
        b"    def description(self):\n"
        b"        return 'hi'\n"
    )
    node = PythonParser().parse(
        content=src, rel_path="box.py", project_root=tmp_path, file_hash="h",
    )
    fragment = node.to_fragment()
    from togra.schema import assert_descriptions_empty

    # Must not raise.
    assert_descriptions_empty(fragment)
    # Sanity: the method itself is present with its own empty description.
    assert fragment["classes"]["Box"]["methods"]["description"]["description"] == ""


def test_descriptions_remain_empty(tmp_path: Path):
    _scaffold(tmp_path)
    parser = PythonParser()
    node = parser.parse(
        content=SOURCE,
        rel_path="src/auth/login.py",
        project_root=tmp_path,
        file_hash="h",
    )
    fragment = node.to_fragment()
    from togra.schema import assert_descriptions_empty

    assert_descriptions_empty(fragment)
