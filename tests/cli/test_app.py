import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

import cli_app.cli.app as app_module
from cli_app.cli.app import app

runner = CliRunner()


def test_version_output_contains_app_name() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "cli-app" in result.output


@pytest.mark.parametrize("flag", ["--authors", "-A"])
def test_authors_flag_shows_author_name(flag: str) -> None:
    result = runner.invoke(app, [flag])
    assert result.exit_code == 0
    assert "Igor Lashkov" in result.output


def test_example_command_with_argument_exits_zero() -> None:
    result = runner.invoke(app, ["command", "example-command", "hello"])
    assert result.exit_code == 0


def test_example_command_uses_console_at_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    console = Console(file=output, force_terminal=False)
    monkeypatch.setattr(app_module, "get_console", lambda: console)

    result = runner.invoke(app, ["command", "example-command", "hello"])

    assert result.exit_code == 0
    assert "hello" in output.getvalue()


def test_example_command_missing_argument_fails() -> None:
    result = runner.invoke(app, ["command", "example-command"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "Error: argument required (or pipe input via stdin)\n"


def test_example_command_missing_argument_reports_json_error() -> None:
    result = runner.invoke(app, ["--output-format", "json", "command", "example-command"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "InvalidInputError",
            "message": "argument required (or pipe input via stdin)",
        }
    }


def test_example_command_with_integer_option() -> None:
    result = runner.invoke(app, ["command", "example-command", "hello", "--option", "42"])
    assert result.exit_code == 0


@pytest.mark.parametrize("flag", ["--verbose", "-V"])
def test_verbose_flag_exits_zero(flag: str) -> None:
    result = runner.invoke(app, [flag, "command", "example-command", "hello"])
    assert result.exit_code == 0


def test_output_format_json_produces_valid_json() -> None:
    result = runner.invoke(app, ["--output-format", "json", "command", "example-command", "hello"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["argument"] == "hello"
    assert data["option"] is None


def test_output_format_json_includes_option_value() -> None:
    result = runner.invoke(
        app, ["--output-format", "json", "command", "example-command", "hello", "--option", "7"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["option"] == 7


def test_json_stdout_stays_clean_with_verbose_logging(tmp_path: Path) -> None:
    env = {**os.environ, "CLI_APP_LOG__DIR": str(tmp_path)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cli_app.main import main; main()",
            "--verbose",
            "--output-format",
            "json",
            "command",
            "example-command",
            "hello",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["argument"] == "hello"
    assert "example_command invoked" in result.stderr


def test_example_command_strips_trailing_newline_from_stdin() -> None:
    result = runner.invoke(
        app, ["--output-format", "json", "command", "example-command"], input="hello\n"
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["argument"] == "hello"


def test_example_command_rejects_blank_stdin() -> None:
    result = runner.invoke(app, ["command", "example-command"], input="\n")
    assert result.exit_code == 2


def test_output_format_text_is_default() -> None:
    result = runner.invoke(app, ["command", "example-command", "hello"])
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_output_format_text_preserves_rich_markup_in_user_input() -> None:
    result = runner.invoke(app, ["command", "example-command", "[red]hello[/red]"])
    assert result.exit_code == 0
    assert "[red]hello[/red]" in result.stdout


def test_output_format_invalid_value_fails() -> None:
    result = runner.invoke(app, ["--output-format", "xml", "command", "example-command", "hi"])
    assert result.exit_code != 0
