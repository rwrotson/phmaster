from typing import cast

from typer import Exit

from cli_app.utils.console import get_console
from cli_app.utils.meta import ContactDict, DependencyDict, get_project_meta


def version_cb(v: bool = False) -> None:
    """Show the version of the CLI."""
    if v:
        meta, console = get_project_meta(), get_console()

        version_str = f"[bold]{meta['name']} {meta['version']}[/bold]"
        dependencies = cast(list[DependencyDict], meta["dependencies"])
        deps_strs = [f" - {dep['name']} {dep['version']}" for dep in dependencies]
        console.print(
            version_str + "\n\nUses:\n" + "\n".join(deps_strs) if deps_strs else version_str
        )

        raise Exit(0)


def authors_cb(v: bool = False) -> None:
    """Show contacts of authors of the CLI."""
    if v:
        meta, console = get_project_meta(), get_console()

        authors = cast(list[ContactDict], meta["authors"])
        authors_strings = [
            f"{author['name']} <[bold]{author['email']}[/bold]>" for author in authors
        ]
        console.print("\n".join(authors_strings))

        raise Exit(0)


def summary_cb(v: bool = False) -> None:
    """Show the summary of the CLI."""
    if v:
        meta, console = get_project_meta(), get_console()

        console.print(f"{meta['summary']}")

        raise Exit(0)
