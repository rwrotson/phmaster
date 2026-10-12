# Changelog

All notable changes to this project will be documented in this file.

## v0.5.0 (2026-10-09)

### BREAKING CHANGE

- settings are read by a single nested `Settings`: `CLI_APP_LOG_*` is now `CLI_APP_LOG__*`, `CLI_APP_CONSOLE_*` is now `CLI_APP_CONSOLE__*`, and `CLI_APP_LOG_USE_JSON_FORMATTER=true` is now `CLI_APP_LOG__FORMAT=json`; old variable names are ignored
- `ConsoleConfig` and `LogConfig` are replaced by `ConsoleSettings` and `LogSettings`, and `cli_app.core` moved to `cli_app.config`
- `ctx.obj` holds a typed `AppContext` instead of a dict
- expected failures raise `ServiceError` subclasses that set the exit code: the example command without input now exits with 2 instead of 1, and with `--output-format json` the error is written to stderr as JSON
- invalid configuration prints a message to stderr and exits with 2 instead of raising a traceback
- piped stdin used in place of an argument no longer keeps trailing line breaks

### Feat

- add services layer with exit-code error mapping, typed AppContext, and import-linter contracts
- consolidate settings into nested Settings and generate config docs from it

### Fix

- strip trailing line breaks from piped stdin argument fallback
- accept custom Rich console in progress bar
- install commit-msg hook with pre-commit
- make audit task scan locked dependencies
- isolate CLI output streams and escape user text
- initialize console at runtime and accept empty width
- store CLI logs in user directory and safely reconfigure handlers

### Build

- enable strict mypy with the Pydantic plugin over sources, tests, and docs scripts, and tighten the Ruff config
- replace taskipy with poethepoet and add a combined `poe check` task
- add YAML, TOML, merge-conflict, large-file, and actionlint pre-commit hooks, run Ruff, mypy, and import-linter from the locked environment, and move pytest to pre-push
- add import-linter with layer contracts
- add security floors for transitive dependencies via `constraint-dependencies`
- migrate to Python 3.14 and update dependencies
- bump the all-deps group with 12 updates
- bump actions/checkout from 6 to 7

### CI

- split CI into quality, test, lowest-dependency, and build jobs
- pin actions to commit SHAs, restrict workflow permissions, and cancel superseded pull request runs
- scan with the pinned trivy action instead of an install script
- build docs with `mkdocs build --strict`
- run CI before deploying docs on release
- switch Dependabot to the uv ecosystem with grouped updates and add pre-commit hook updates
- type-check tests and build the package and docs in CI

### Test

- run tests in random order with strict pytest settings, warnings as errors, and a timeout
- raise the coverage gate to 95% with branch coverage
- isolate tests from `CLI_APP_*` variables, the local `.env`, logging state, and the cached console

### Docs

- add an architecture guide and generate the configuration page from `Settings`
- add dependency, change workflow, and testing rules to AGENTS.md
- add "What Is Included" and example removal guides to the README
- standardize documentation and enforce public docstrings
- align the release guide and template renaming checklist

### Chore

- declare Rich directly and remove unused pytest-mock

## v0.4.4 (2026-07-06)

### Fix

- deploy docs via GitHub Actions Pages and bound uv_build

## v0.4.3 (2026-07-06)

### Fix

- unbreak docs build by upgrading mkdocs tooling for pygments 2.20

## v0.4.2 (2026-07-06)

### Fix

- upgrade dependencies for security advisories and scope pip-audit to project deps

## v0.4.1 (2026-03-15)

### Fix

- pytest-cov improvements

## v0.4.0 (2026-03-15)

### Feat

- add github token to workflow
- major update

### Fix

- trivy cicd job
- console layout test

### Refactor

- update deps
- project cleanup
- tests refactor
- tests refactor
- tests refactor
- tests refactor

## v0.2.0 (2025-07-05)

### Feat

- proper structure & utils
- proper structure & utils
- proper structure & utils
- first blueprint
- first blueprint

## v0.1.0 (2025-07-01)
