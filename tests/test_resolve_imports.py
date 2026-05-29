from pathlib import Path

from togra.resolve.imports import resolve_import_type, resolve_relative_path


def test_resolve_import_type():
    assert resolve_import_type("APP_CONFIG") == "constant"
    assert resolve_import_type("User") == "class"
    assert resolve_import_type("hash_password") == "function"
    assert resolve_import_type("") == "unknown"


def _scaffold(root: Path) -> None:
    (root / "src/auth").mkdir(parents=True)
    (root / "src/models").mkdir(parents=True)
    (root / "src/utils").mkdir(parents=True)
    (root / "src/__init__.py").touch()
    (root / "src/auth/__init__.py").touch()
    (root / "src/models/__init__.py").touch()
    (root / "src/utils/__init__.py").touch()
    (root / "src/auth/login.py").write_text("# login")
    (root / "src/models/user.py").write_text("# user")
    (root / "src/utils/crypto.py").write_text("# crypto")


def test_relative_one_dot(tmp_path: Path):
    _scaffold(tmp_path)
    login = tmp_path / "src/auth/login.py"
    assert (
        resolve_relative_path(".user", login, tmp_path) == ".user"
    )  # no sibling user.py
    # Sibling within same package
    (tmp_path / "src/auth/helpers.py").write_text("")
    assert resolve_relative_path(".helpers", login, tmp_path) == "src/auth/helpers.py"


def test_relative_two_dots(tmp_path: Path):
    _scaffold(tmp_path)
    login = tmp_path / "src/auth/login.py"
    assert (
        resolve_relative_path("..models.user", login, tmp_path) == "src/models/user.py"
    )
    assert (
        resolve_relative_path("..utils.crypto", login, tmp_path) == "src/utils/crypto.py"
    )


def test_external_returned_unchanged(tmp_path: Path):
    _scaffold(tmp_path)
    login = tmp_path / "src/auth/login.py"
    assert resolve_relative_path("fastapi", login, tmp_path) == "fastapi"
