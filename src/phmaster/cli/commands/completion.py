import subprocess
import sys
from typing import Annotated

import typer

app = typer.Typer(help="Manage shell completion scripts.")


@app.command("install")
def install_completion(
    shell: Annotated[
        str | None,
        typer.Option(
            "--shell",
            "-s",
            help="Target shell: bash, zsh, fish, powershell. Auto-detected if omitted.",
        ),
    ] = None,
) -> None:
    """Install shell completion into the selected shell profile."""
    cmd = [sys.argv[0], "--install-completion"]
    if shell:
        cmd.append(shell)
    result = subprocess.run(cmd, check=False)  # noqa: S603
    raise typer.Exit(result.returncode)


@app.command("show")
def show_completion(
    shell: Annotated[
        str | None,
        typer.Option(
            "--shell",
            "-s",
            help="Target shell: bash, zsh, fish, powershell. Auto-detected if omitted.",
        ),
    ] = None,
) -> None:
    """Print the shell completion script to stdout."""
    cmd = [sys.argv[0], "--show-completion"]
    if shell:
        cmd.append(shell)
    result = subprocess.run(cmd, check=False)  # noqa: S603
    raise typer.Exit(result.returncode)
