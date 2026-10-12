# Getting Started

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

```bash
git clone <repo-url>
cd typer-template
uv sync --all-groups --locked
uv run pre-commit install
```

`pre-commit install` sets up three Git hooks:

- `pre-commit` — file hygiene checks, `uv lock` check, actionlint, ruff (with `--fix`), import-linter, mypy
- `commit-msg` — Conventional Commit format (Commitizen)
- `pre-push` — pytest without coverage

Ruff and mypy run from the locked project environment (`uv run --no-sync`), so hook and CI versions match.

## Running the CLI

```bash
uv run cli-app --help
uv run cli-app --version
uv run cli-app --authors
```

### Global flags

Place global flags before the subcommand:

```bash
uv run cli-app --verbose command example-command hello

uv run cli-app --output-format json command example-command hello

echo "hello" | uv run cli-app command example-command
```

### Shell completion

```bash
uv run cli-app completion install

uv run cli-app completion install --shell zsh

uv run cli-app completion show
```

## Development Commands

Tasks are available via [poethepoet](https://poethepoet.natn.io/) — run with `uv run poe <name>`:

```bash
uv run poe check        # fmt-check, lint, lint-imports, typecheck, test
uv run poe fmt          # ruff format .
uv run poe fmt-check    # ruff format --check .
uv run poe lint         # ruff check .
uv run poe lint-imports # import-linter layer contracts
uv run poe typecheck    # mypy (strict: src, tests, docs)
uv run poe test         # pytest (parallel, 95% branch coverage enforced)
uv run poe test-fast    # pytest without coverage, parallel, random order
uv run poe docs         # properdocs serve
uv run poe audit        # pip-audit over locked dependencies
```

Tests run in parallel and in random order. pytest-randomly prints the seed at the top of the run; reproduce an order-dependent failure with `uv run pytest -p randomly --randomly-seed=<seed>`. `poe test-fast` skips coverage; `poe check` runs the same quality and test steps as the CI `quality` and `test` jobs.

Or run the tools directly:

```bash
uv run pytest                        # full suite without coverage
uv run pytest --cov                  # with the coverage gate
uv run pytest tests/path/to/test.py  # single file
```

## Versioning & Changelog

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) — enforced by the `commit-msg` pre-commit hook.

```bash
uv run cz bump            # bump version, update CHANGELOG, create tag
uv run cz changelog       # update CHANGELOG without bumping
uv run cz changelog --dry-run
```

Bump type is inferred from commits: `fix:` → patch · `feat:` → minor · `feat!:` / `BREAKING CHANGE:` → major.

## Adding a Command Group

See the [architecture guide](architecture.md) for the layers and error handling.

1. Create the use case in `src/cli_app/services/greeting.py`:

```python
from cli_app.services.errors import InvalidInputError


def greet(name: str) -> str:
    """Build a greeting for a non-empty name."""
    if not name.strip():
        raise InvalidInputError("name must not be empty")
    return f"Hello, {name}!"
```

2. Create the command in `src/cli_app/cli/commands/my_command.py`:

```python
from rich.markup import escape
from typer import Context, Typer

from cli_app.cli.context import get_app_context
from cli_app.services.greeting import greet
from cli_app.utils.output import render_output

app = Typer()


@app.command()
def my_action(ctx: Context, name: str) -> None:
    """Greet a named user in text or JSON."""
    app_context = get_app_context(ctx)
    message = greet(name)
    render_output(
        {"message": message},
        app_context.output_format,
        text_render=lambda: app_context.console.print(escape(message)),
    )
```

3. Export it from `src/cli_app/cli/commands/__init__.py`:

```python
from .my_command import app as my_command_app
```

4. Register it in `src/cli_app/cli/app.py`:

```python
from cli_app.cli.commands import my_command_app

app.add_typer(my_command_app, name="my-command")
```

### Stdin support

Use `read_stdin_if_piped()` to accept piped input as a fallback when an argument is omitted, and let the use case reject empty input:

```python
from cli_app.utils.stdin import read_stdin_if_piped


@app.command()
def process(ctx: Context, text: str | None = None) -> None:
    result = run_use_case(text if text is not None else read_stdin_if_piped())
    ...
```

## Configuration

Behaviour can be overridden via environment variables or a `.env` file. Sections are nested with `__`:

| Prefix | Controls |
|--------|----------|
| `CLI_APP_CONSOLE__*` | Rich console (width, colors, markup, quiet mode) |
| `CLI_APP_LOG__*` | Log levels, console renderer, log directory, file rotation |

```env
CLI_APP_LOG__LEVEL=DEBUG
CLI_APP_LOG__FORMAT=json
CLI_APP_CONSOLE__WIDTH=120
```

All variables are listed on the [configuration page](configuration.md).
