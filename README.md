# typer-template

A Python CLI template with Typer, Rich output, structlog logging, and environment-based settings.

## What Is Included

- Typer app with global `--verbose`, `--output-format text|json`, `--version`, and `--authors` options; JSON on stdout and diagnostics on stderr; piped stdin support; shell completion commands
- A `services/` layer for use cases; `ServiceError` subclasses map to stderr messages and exit codes; import-linter contracts keep services independent of Typer, Rich, and settings
- One Pydantic `Settings` with nested `CLI_APP_CONSOLE__*` and `CLI_APP_LOG__*` sections, a test that keeps `.env.example` in sync, and a generated configuration page
- structlog logging to stderr (console or JSON) and a rotating JSON log file with UTC timestamps
- Strict MyPy with the Pydantic plugin, Ruff, pytest in parallel and random order with a 95% branch coverage gate, poethepoet tasks, pre-commit hooks, Commitizen
- CI with a lowest-dependency test job, package and strict docs builds, pip-audit, and trivy; actions pinned to commit SHAs; ProperDocs on GitHub Pages after CI passes on a release tag

## Stack

- **[Typer](https://typer.tiangolo.com/)** — CLI framework
- **[Rich](https://rich.readthedocs.io/)** — terminal output and progress bars
- **[structlog](https://www.structlog.org/)** — structured logging with context binding; dev console output or JSON for aggregators
- **[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** — environment-based configuration
- **[uv](https://docs.astral.sh/uv/)** — package management
- **[Ruff](https://docs.astral.sh/ruff/)** — linting and formatting
- **[MyPy](https://mypy.readthedocs.io/)** — strict type checking
- **[pytest](https://docs.pytest.org/)** + **[pytest-xdist](https://github.com/pytest-dev/pytest-xdist)** + **[pytest-randomly](https://github.com/pytest-dev/pytest-randomly)** — parallel tests in random order with coverage enforcement
- **[import-linter](https://import-linter.readthedocs.io/)** — layer boundary contracts
- **[poethepoet](https://poethepoet.natn.io/)** — task runner
- **[commitizen](https://commitizen-tools.github.io/commitizen/)** — Conventional Commits + automated versioning and CHANGELOG
- **[ProperDocs](https://properdocs.org/)** + **[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)** — documentation site

## Requirements

- Python 3.14+
- uv

## Getting Started

```bash
uv sync --all-groups --locked

uv run cli-app --help

uv run pre-commit install
```

## Development

Run development tasks with [poethepoet](https://poethepoet.natn.io/):

```bash
uv run poe check       # format check, lint, import contracts, type check, tests with coverage
uv run poe fmt
uv run poe test-fast
uv run poe docs
uv run poe audit
```

Or run the tools directly:

```bash
uv run pytest
uv run pytest tests/path/to/test.py
```

## Docs

```bash
uv run --group docs properdocs serve
uv run --group docs properdocs build
```

Source is in `docs/`. ProperDocs generates the API reference from public docstrings. The release workflow deploys the site to GitHub Pages.

## Global CLI Flags

The root app exposes flags available to every subcommand:

| Flag | Short | Default | Effect |
|------|-------|---------|--------|
| `--verbose` | `-V` | off | Sets log level to DEBUG at runtime |
| `--output-format` | `-f` | `text` | `text` (Rich) or `json` (machine-readable) |
| `--version` | `-v` | — | Print version and dependency list, then exit |
| `--authors` | `-A` | — | Print author contacts, then exit |

JSON output is written to stdout; diagnostics are written to stderr.

```bash
cli-app --verbose command example-command hello
cli-app --output-format json command example-command hello
echo "hello" | cli-app command example-command
```

## Shell Completion

```bash
cli-app completion install
cli-app completion install --shell zsh
cli-app completion show
```

Or directly via the built-in Typer flags:

```bash
cli-app --install-completion
cli-app --show-completion
```

## Versioning & Changelog

This template uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by a `commit-msg` pre-commit hook.

```bash
uv run cz bump

uv run cz changelog --dry-run
```

Bump type is inferred automatically: `fix:` → patch, `feat:` → minor, `feat!:` / `BREAKING CHANGE` → major.

## Configuration

`cli_app.config.Settings` defines defaults in code and reads `CLI_APP_*` environment variables and `.env`; the process environment wins. Sections are nested with `__`:

| Prefix | Controls |
|--------|----------|
| `CLI_APP_CONSOLE__*` | Rich console (width, colors, markup, quiet mode) |
| `CLI_APP_LOG__*` | Log levels, console renderer, log directory, file rotation |

```env
CLI_APP_LOG__LEVEL=DEBUG
CLI_APP_LOG__FORMAT=json
CLI_APP_CONSOLE__WIDTH=120
```

See `.env.example` and the generated configuration page in the documentation site.

## Project Structure

```
src/
└── cli_app/
    ├── main.py              # entry point
    ├── cli/
    │   ├── app.py           # root Typer app (--verbose, --output-format, --version, --authors)
    │   ├── context.py       # AppContext stored in ctx.obj
    │   ├── errors.py        # ServiceError → stderr message and exit code
    │   ├── callbacks/       # eager option callbacks (--version, --authors)
    │   └── commands/
    │       ├── command.py   # example command group (stdin + output-format patterns)
    │       └── completion.py # shell completion sub-app
    ├── config/              # Settings with console and log sections
    ├── services/            # use cases and ServiceError; no Typer, Rich, or settings
    └── utils/
        ├── console.py       # singleton Rich Console
        ├── log.py           # structlog setup (ConsoleRenderer dev / JSON prod)
        ├── output.py        # OutputFormat enum, render_output(), echo_json()
        ├── stdin.py         # is_stdin_piped(), read_stdin_if_piped(), iter_stdin_lines()
        ├── meta.py          # distribution metadata at runtime
        ├── format.py        # Rich Theme
        ├── emoji.py         # Emoji StrEnum
        ├── progress.py      # Rich Progress bar factory
        └── misc.py          # find_project_root()
```

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main` and `dev`. Actions are pinned to commit SHAs.

| Job | What it does |
|-----|-------------|
| `quality` | ruff format check, ruff lint, import-linter contracts, strict mypy |
| `test` | parallel tests in random order, 95% branch coverage enforced |
| `lowest` | tests against the lowest allowed direct dependencies |
| `build` | package build, `properdocs build --strict`, pip-audit, trivy filesystem scan (CRITICAL/HIGH) |

Dependabot opens weekly grouped PRs for uv dependencies, GitHub Actions, and pre-commit hooks.

`.github/workflows/release.yml` runs on version tags (`v*`) or via `workflow_dispatch`. It runs CI first, then:

| Job | What it does |
|-----|-------------|
| `docs` | builds the docs with ProperDocs and deploys it to GitHub Pages via GitHub Actions |

The workflow does not publish the package to PyPI. Set Pages Source to **GitHub Actions** and allow `v*` tags in the `github-pages` environment for tag-triggered deployments.

## Using This Template

The distribution, import package, and CLI command have separate names. Follow the [renaming checklist](https://rwrotson.github.io/typer-template/notes/#renaming-the-template) when copying this template into a new project.

### Remove the Example

The example command is meant to be copied, then deleted. When your first real command exists, remove:

- `src/cli_app/services/example.py` and `tests/services/test_example.py`
- `src/cli_app/cli/commands/command.py`, its export in `src/cli_app/cli/commands/__init__.py`, and its `add_typer` line in `src/cli_app/cli/app.py`
- the `example-command` tests in `tests/cli/test_app.py` (keep the global option tests by pointing them at your command)
- the `cli_app.services.example` and `cli_app.cli.commands.command` rows in `docs/reference/index.md`, and the example references in `docs/architecture.md` and `docs/notes.md`

Then remove imports the deleted tests leave unused (Ruff reports them as F401 but does not fix them automatically) and run `uv run poe check` and `uv run --group docs properdocs build --strict`.

## Author

Igor Lashkov — rwrotson@yandex.ru
