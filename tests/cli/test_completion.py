import subprocess
import sys

import pytest
from typer.testing import CliRunner

from cli_app.cli.commands import completion_app

runner = CliRunner()
_EXIT_CODE = 3


@pytest.mark.parametrize(
    ("command", "flag"), [("install", "--install-completion"), ("show", "--show-completion")]
)
@pytest.mark.parametrize("shell", [None, "zsh"])
def test_completion_delegates_to_typer_flag(
    monkeypatch: pytest.MonkeyPatch, command: str, flag: str, shell: str | None
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, _EXIT_CODE)

    monkeypatch.setattr(subprocess, "run", fake_run)
    args = [command] if shell is None else [command, "--shell", shell]

    result = runner.invoke(completion_app, args)

    assert result.exit_code == _EXIT_CODE
    expected = [sys.argv[0], flag] if shell is None else [sys.argv[0], flag, shell]
    assert calls == [expected]
