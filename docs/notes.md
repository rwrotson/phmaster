# Notes

## Build Backend

`uv_build` loads the `cli_app` package from `src/`:

```toml
[tool.uv.build-backend]
module-name = "cli_app"
module-root = "src"
```

## Package Metadata at Runtime

`cli_app.utils.meta` reads the installed distribution's name, version, and dependencies. Editable `uv_build` installs omit `top_level.txt`, so `Meta.load_from_installed_package()` resolves the distribution through `direct_url.json` before using `packages_distributions()`.

## structlog Integration

`cli_app.utils.log` connects [structlog](https://www.structlog.org/) to stdlib logging through `ProcessorFormatter`:

- `get_logger()` creates first-party loggers; third-party stdlib loggers use the same handlers.
- Console logs use Rich-style output or JSON when `CLI_APP_LOG__FORMAT=json`.
- File logs use JSON in the user log directory; `CLI_APP_LOG__DIR` overrides the directory.
- Timestamps are ISO 8601 in UTC.
- `structlog.contextvars.bind_contextvars()` adds fields to subsequent logs in the current context.

`main()` calls `setup_logging()`. Before setup, structlog writes to stderr to keep JSON command output on stdout valid.

## Output Format Pattern

Commands read the `AppContext` stored by the root callback and call `render_output()`:

```python
app_context = get_app_context(ctx)
render_output(
    {"key": value},
    app_context.output_format,
    text_render=lambda: app_context.console.print(...),
)
```

JSON output goes to stdout; diagnostics go to stderr. In text mode, `render_output()` uses `text_render` when provided and the Rich console otherwise.

## Stdin Piping Pattern

`read_stdin_if_piped()` returns `None` for a TTY and the piped content without trailing line breaks, so `echo hi | cli-app ...` matches `cli-app ... hi`. `read_stdin()` returns stdin unchanged:

```python
result = run_example(argument if argument is not None else read_stdin_if_piped(), option)
```

`CliRunner` provides non-TTY stdin in tests, even when no input is passed. `run_example()` rejects the resulting empty string with `InvalidInputError`.

## Documentation Toolchain

The site is built with [ProperDocs](https://properdocs.org/), a maintained continuation of MkDocs 1.x that reads the same configuration (`properdocs.yml`) and runs MkDocs themes and plugins unchanged. MkDocs 2.0 drops the plugin and theme system, and Material for MkDocs requires `mkdocs<2`, so the `mkdocs` package stays on 1.x as a library dependency of the plugins. Running `properdocs` instead of `mkdocs` also avoids the MkDocs 2.0 warnings printed by Material and the plugins.

[Zensical](https://zensical.org/), the successor to Material for MkDocs, does not support `mkdocs-gen-files` yet; the API reference and configuration pages depend on it.

## Commitizen & Versioning

[Commitizen](https://commitizen-tools.github.io/commitizen/) reads Conventional Commit messages to select the next version and update `CHANGELOG.md`. Its settings are in `pyproject.toml`:

```toml
version_provider = "uv"
update_changelog_on_bump = true
major_version_zero = true
```

The `commit-msg` hook checks Conventional Commit format.

## Renaming the Template

Choose three names before editing: a distribution name (for example, `my-tool`), an import
package (`my_tool`), and a CLI command (`my-tool`). They can differ, but each use of a name
must stay consistent.

1. Rename `src/cli_app/` to `src/my_tool/`. Replace `cli_app` in imports throughout `src/`
   and `tests/`, including mock targets and the metadata test. Update `module-name` under
   `[tool.uv.build-backend]`, `[tool.coverage.run].source`, and
   `[tool.ruff.lint.isort].known-first-party` in `pyproject.toml`.
2. Set `[project].name` and `[project.scripts]` in `pyproject.toml`. Point the script at
   `my_tool.main:main`. Update the project description, authors, keywords, and other metadata.
3. Change `env_prefix` and the `env_fields()` default prefix in
   `src/my_tool/config/settings.py`, and `PREFIX` in `docs/gen_config_page.py`. Adjust the
   default log directory and file name in `LogSettings`. Update `.env.example`, README
   examples, and tests using `CLI_APP_` variables.
4. Update `properdocs.yml` (`site_name`, repository links, and the source watch path) and
   `docs/gen_ref_pages.py`, which scans the import package for API pages. Update names and
   links in README, docs, and `AGENTS.md`. If you host docs on GitHub Pages, configure Pages
   Source as **GitHub Actions** and allow release tags in the `github-pages` environment.
5. Regenerate the lockfile with `uv lock`, then run `uv sync --all-groups --locked`,
   `uv run pytest`, `uv build`, and `uv run --group docs properdocs build`. Check that
   `uv run my-tool --help` and `uv run my-tool --version` show the new project identity.

The release workflow only deploys documentation. Add a separate publishing workflow if the
new project should publish packages to PyPI.
