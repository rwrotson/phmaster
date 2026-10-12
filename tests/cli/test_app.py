import pytest
from typer.testing import CliRunner

from phmaster.cli.app import app

runner = CliRunner()


def test_version_output_contains_app_name() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "phmaster" in result.output


@pytest.mark.parametrize("flag", ["--authors", "-A"])
def test_authors_flag_shows_author_name(flag: str) -> None:
    result = runner.invoke(app, [flag])
    assert result.exit_code == 0
    assert "Igor Lashkov" in result.output


def test_output_format_invalid_value_fails() -> None:
    result = runner.invoke(app, ["--output-format", "xml", "completion", "show"])
    assert result.exit_code != 0
