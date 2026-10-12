import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mediagen import make_media
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


@pytest.mark.parametrize("flag", ["--verbose", "-V"])
def test_verbose_flag_exits_zero(flag: str, tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=1)
    result = runner.invoke(app, [flag, "probe", str(source)])
    assert result.exit_code == 0


def test_json_stdout_stays_clean_with_verbose_logging(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=1)
    env = {**os.environ, "PHMASTER_LOG__DIR": str(tmp_path / "logs")}
    result = subprocess.run(  # noqa: S603 - fixed test command
        [
            sys.executable,
            "-c",
            "from phmaster.main import main; main()",
            "--verbose",
            "--output-format",
            "json",
            "process",
            str(source),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["results"][0]["dry_run"] is True
    assert "processing files" in result.stderr
