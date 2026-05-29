from pathlib import Path

from typer.testing import CliRunner

from togra.cli import app
from togra.commands.tokens import CHARS_PER_TOKEN, count_tokens

runner = CliRunner()


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_count_tokens_nonempty_at_least_one():
    assert count_tokens("a") == 1


def test_count_tokens_scales_with_length():
    text = "x" * 350  # at 3.5 chars/token → 100 tokens
    assert count_tokens(text) == 100


def test_count_tokens_custom_ratio():
    assert count_tokens("x" * 20, chars_per_token=4.0) == 5
    assert count_tokens("x" * 21, chars_per_token=4.0) == 6  # ceil


def test_cli_single_file(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("def x(): pass\n")
    result = runner.invoke(
        app, ["tokens", str(f), "--project", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "tokens" in result.output
    assert "a.py" in result.output


def test_cli_directory_with_lang_filter(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.json").write_text('{"k": 1}\n')
    result = runner.invoke(
        app,
        ["tokens", str(tmp_path), "--project", str(tmp_path), "--lang", "python"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    # Language summary contains python but not json under filter.
    assert "python" in result.output
    assert "json" not in result.output


def test_cli_graph_mode(tmp_path: Path):
    # Bootstrap a graph.
    (tmp_path / "a.py").write_text("x = 1\n")
    assert runner.invoke(
        app, ["init", "--project", str(tmp_path)], catch_exceptions=False
    ).exit_code == 0
    assert runner.invoke(
        app, ["build", "--project", str(tmp_path)], catch_exceptions=False
    ).exit_code == 0
    result = runner.invoke(
        app, ["tokens", "--graph", "--project", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "graph.json" in result.output
    assert "tokens" in result.output


def test_cli_graph_mode_missing(tmp_path: Path):
    # No togra-output/ yet.
    result = runner.invoke(
        app, ["tokens", "--graph", "--project", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "not found" in result.output


def test_chars_per_token_default():
    assert CHARS_PER_TOKEN == 3.5
