# AGENTS.md

This file describes repository conventions for coding agents.

## Project Overview

A template for building Python CLI apps using [Typer](https://typer.tiangolo.com/) with Rich output, structlog-based structured logging, and Pydantic Settings-based configuration.

Distribution name: `cli-app` | Python package: `cli_app` | Entry point: `cli-app`

## Commands

This project uses [uv](https://docs.astral.sh/uv/) for package management.

```bash
# Install dependencies
uv sync --all-groups --locked

# Run the CLI
uv run cli-app

# Tasks via poethepoet (uv run poe <name>)
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

# Or run tools directly
uv run ruff check .
uv run ruff format .
uv run mypy
uv run pytest
uv run pytest --cov

# Install pre-commit, commit-msg, and pre-push hooks
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files

# Versioning
uv run cz bump           # bump version, update CHANGELOG, tag
uv run cz changelog      # update CHANGELOG only

# Serve docs locally (live reload)
uv run poe docs

# Build static docs site as CI does (CI deploys it to GitHub Pages via actions/deploy-pages)
uv run --group docs properdocs build --strict
```

## Dependencies

- Put runtime imports in `[project].dependencies`, development tools in the `dev` group, and documentation tools in the `docs` group.
- Change dependencies through uv (`uv add`, `uv remove`) so `pyproject.toml` and `uv.lock` change together. Verify the lock with `uv sync --locked --all-groups`.
- Raise a direct dependency's lower bound when code needs a newer API. The locked environment does not check lower bounds; the CI `lowest` job does.
- Do not import packages that are installed only as transitive dependencies (for example `click`, which Typer vendors).
- Security floors for transitive dependencies go in `[tool.uv] constraint-dependencies`.
- Use the project environment for tools. Do not install packages manually into `.venv`.

## Change Workflow

- Inspect `git status` before editing. Preserve existing uncommitted changes and limit edits to the requested task.
- Run `uv run poe check` after code changes. After documentation, `properdocs.yml`, or public docstring changes, also run `uv run --group docs properdocs build --strict`.
- Do not lower coverage thresholds, disable checks, relax import-linter contracts, or add lint and type suppressions solely to pass CI. Explain necessary suppressions at the affected line.
- Use non-rewriting checks (`poe fmt-check`, `poe lint`) for verification; run formatters or `--fix` only when intentionally editing files. Pre-commit's Ruff hooks rewrite files.
- Report which checks ran, which were skipped, and why. `poe test-fast` is not the full CI suite: it skips coverage, and CI also runs the lowest-dependency job, package and docs builds, and security scans.
- When changing public settings, global options, or commands, update `.env.example`, README, and the docs. Do not edit generated pages (configuration, API reference); edit `Settings` field descriptions and source docstrings instead.
- Keep the user's `.env` and secrets untracked.

## CI/CD

`.github/workflows/ci.yml` triggers on push/PR to `main` and `dev` and is reusable via
`workflow_call`. Workflow permissions are `contents: read`; actions are pinned to commit SHAs.
Parallel jobs:

- **`quality`** — `poe fmt-check`, `poe lint`, `poe lint-imports`, `poe typecheck`.
- **`test`** — `poe test` (95% branch coverage).
- **`lowest`** — installs the lowest allowed direct dependencies (`--resolution lowest-direct`)
  and runs pytest; it checks the declared lower bounds, which the lock does not.
- **`build`** — `uv build`, `properdocs build --strict`, `poe audit`, trivy filesystem scan
  (CRITICAL/HIGH).

`.github/workflows/release.yml` triggers on version tags (`v*`) and manual `workflow_dispatch`.
It runs CI first, then:

- **`docs`** — builds the site with `properdocs build --strict` and deploys it to **GitHub Pages** via
  `actions/upload-pages-artifact` + `actions/deploy-pages` (the `github-pages` environment).
  Permissions: `pages: write`, `id-token: write`, `contents: read`. There is **no PyPI publish**.

Pages Source must be set to **"GitHub Actions"** (Settings → Pages), and the `github-pages`
environment must allow the `v*` tag (Settings → Environments → Deployment branches and tags → no
restriction, or a `v*` rule) — otherwise the tag-triggered deploy is blocked. Site:
https://rwrotson.github.io/typer-template/

Dependabot opens weekly grouped PRs for uv dependencies (`uv.lock`), GitHub Actions, and pre-commit
hooks (`.github/dependabot.yml`).

## Architecture

### Package Layout & Build

Source lives in `src/cli_app/` — the standard `src/` layout. The uv build backend is configured in `pyproject.toml`:

```toml
[tool.uv.build-backend]
module-name = "cli_app"
module-root = "src"
```

Internal imports use the `cli_app.` prefix. Ruff bans relative imports except in package `__init__.py`, which may re-export from sibling modules (`from .module import ...`, never `..`):

```python
from cli_app.cli.app import app
from cli_app.utils.console import get_console
```

### Entry Point & Startup

`src/cli_app/main.py` is minimal: loads `Settings` (invalid configuration exits with code 2), calls `setup_logging(settings.log)`, `get_console()`, then `app()`. The console script entry point is `cli_app.main:main`.

### CLI Structure

```
src/cli_app/cli/app.py          — Root Typer app; registers subcommand groups and global options
src/cli_app/cli/context.py      — AppContext (settings, console, output format) and get_app_context()
src/cli_app/cli/errors.py       — ServiceErrorGroup: reports ServiceError on stderr and exits with its code
src/cli_app/cli/callbacks/      — Eager option callbacks that print metadata and exit
src/cli_app/cli/commands/       — Subcommand groups; each file creates its own Typer sub-app
src/cli_app/services/           — Use cases, result types, and ServiceError subclasses
```

The root callback (`app.py`) stores an `AppContext` in `ctx.obj` before any subcommand runs; commands read it with `get_app_context(ctx)`. It also adjusts the root logger level when `--verbose` is passed.

Follow the layers in `docs/architecture.md`: commands call use cases in `cli_app.services`; services never import Typer, Rich, structlog, settings, `cli_app.cli`, or `cli_app.utils`. Expected failures raise a `ServiceError` subclass with an `exit_code` instead of `typer.Exit`. import-linter contracts in `pyproject.toml` enforce the boundaries (`uv run poe lint-imports`).

To add a new command group: put the use case in `src/cli_app/services/`, create a file in `src/cli_app/cli/commands/`, define a Typer app, export it from `__init__.py`, then add `app.add_typer(...)` in `src/cli_app/cli/app.py`.

### Configuration via Environment Variables

`src/cli_app/config/settings.py` defines `Settings` (Pydantic `BaseSettings`, prefix `CLI_APP_`, nested delimiter `__`) with defaults in code and the sections `ConsoleSettings` (`CLI_APP_CONSOLE__*`) and `LogSettings` (`CLI_APP_LOG__*`). `load_settings()` reads the environment and `.env`; empty values use defaults. `setup_logging()` and `build_console()` take a section instead of reading the environment themselves.

Every setting needs a `Field(description=...)` and a line in `.env.example`; tests in `tests/config/` enforce both. The docs configuration page is generated from `Settings` by `docs/gen_config_page.py`; do not edit it by hand.

`get_console()` and `get_project_meta()` cache their results.

### Logging (structlog)

`setup_logging()` configures structlog bridged through stdlib via `ProcessorFormatter`. First-party commands use `get_logger()` from `cli_app.utils.log` so early logs go to stderr; third-party stdlib loggers share the same handler chain. Console output uses `ConsoleRenderer` by default; set `CLI_APP_LOG__FORMAT=json` for JSON. File output is always JSON.

Use `structlog.contextvars.bind_contextvars(key=value)` to attach context that appears on every log line.

Before `setup_logging()` is called (e.g. in tests), structlog defaults to stderr output so it never pollutes stdout.

### Documentation Generation

`docs/gen_ref_pages.py` generates API pages from source modules. `docs/gen_config_page.py` builds the configuration page from `Settings` field types, defaults, and descriptions.

### Utilities

| Module | Purpose |
|--------|---------|
| `src/cli_app/utils/console.py` | Singleton Rich `Console` with theming |
| `src/cli_app/utils/log.py` | structlog setup; file + console handlers configured from `LogSettings` |
| `src/cli_app/utils/output.py` | `OutputFormat` enum; `render_output()` and `echo_json()` helpers |
| `src/cli_app/utils/stdin.py` | `is_stdin_piped()`, `read_stdin_if_piped()`, `iter_stdin_lines()` |
| `src/cli_app/utils/meta.py` | Reads distribution metadata at runtime; scans `direct_url.json` for editable-install compat |
| `src/cli_app/utils/format.py` | Rich `Theme` with `info`/`warning`/`danger` styles |
| `src/cli_app/utils/emoji.py` | `Emoji` StrEnum for consistent emoji usage |
| `src/cli_app/utils/progress.py` | Rich `Progress` bar wired to the project console |
| `src/cli_app/utils/misc.py` | `find_project_root()` helper |

### Testing

`tests/` mirrors the package (`cli/`, `config/`, `services/`, `utils/`). Test use cases directly in `tests/services/`, and argument parsing, output, and exit codes with `CliRunner` in `tests/cli/`.

Tests run in parallel (pytest-xdist) and in random order (pytest-randomly); warnings are errors and each test has a 30-second timeout. Autouse fixtures in `tests/conftest.py` remove `CLI_APP_*` variables, run each test in a temporary working directory (so a local `.env` is not read), restore logging and structlog configuration, and clear the cached console. Tests must not depend on process-wide state or on each other. Reproduce an order-dependent failure with `uv run pytest -p randomly --randomly-seed=<seed>` (the seed is printed at the top of the run).

### Type Checking

MyPy runs with `strict = true` and the Pydantic plugin over `src/`, `tests/`, and `docs/`. All new code must have complete type annotations. Python 3.14 supports union syntax (`X | Y`), which is preferred over `Optional[X]`.

## Commit Handoff

- Do not create or amend commits on the user's behalf.
- After completing and verifying a meaningful, self-contained part of the work, pause before starting the next part.
- At each pause, send the user a one-line English Conventional Commit message for the completed work. Resume when the user asks you to continue.

## Documentation and Comments

- Write documentation, docstrings, and comments in English. Keep them short and factual. Describe each entity's purpose without editorial commentary or tutorials.
- Do not add module docstrings. Package docstrings in `__init__.py` are optional. Put package behavior and important module details in Markdown documentation such as `README.md` or `docs/`.
- Give public classes, functions, and ordinary methods a docstring. Prefer one line describing their overall purpose; do not repeat names, signatures, or type annotations. Ruff checks these in application code. Test functions, fixtures, and standard `dunder` methods are exempt.
- Add docstrings to protected or private objects only when they explain behavior that is not clear from code.
- Keep inline comments only for non-obvious behavior or decisions. Put a short comment on the relevant line when it fits; otherwise place it immediately above. Retain necessary tool directives such as `# noqa` and `# type: ignore`.
- Prefer clearer names and more precise types over comments that restate code.
