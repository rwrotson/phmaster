# Notes

## Build Backend

`uv_build` loads the `phmaster` package from `src/`:

```toml
[tool.uv.build-backend]
module-name = "phmaster"
module-root = "src"
```

## Package Metadata at Runtime

`phmaster.utils.meta` reads the installed distribution's name, version, and dependencies. Editable `uv_build` installs omit `top_level.txt`, so `Meta.load_from_installed_package()` resolves the distribution through `direct_url.json` before using `packages_distributions()`.

## structlog Integration

`phmaster.utils.log` connects [structlog](https://www.structlog.org/) to stdlib logging through `ProcessorFormatter`:

- `get_logger()` creates first-party loggers; third-party stdlib loggers use the same handlers.
- Console logs use Rich-style output or JSON when `PHMASTER_LOG__FORMAT=json`.
- File logs use JSON in the user log directory; `PHMASTER_LOG__DIR` overrides the directory.
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

## ffmpeg Integration

Services call ffmpeg and ffprobe through `subprocess` without a shell; commands are argument lists. Decoders write interleaved little-endian float32 PCM at 48 kHz to stdout; encoders read the same format from stdin. stderr goes to a temporary file, so a chatty process cannot block on a full pipe, and its last lines become the `FfmpegError` message.

Channel layout conversion uses `aresample` rematrixing (`ochl`, `clev`, `slev`, `lfe_mix_level`), so any layout ffmpeg knows can be downmixed. `amerge` needs `aformat` on both inputs to negotiate formats.

ffprobe reports Matroska tags as written; MP4 drops custom tags and reports the track title as `name`. phmaster therefore marks its tracks with both a `PHMASTER=<preset>:<layout>:<source index>` tag and a title ending in ` · phmaster <preset> (<layout>, a:<source index>)`; only that exact suffix marks a track, so a title such as `Phmaster commentary` does not. A stream copy does not write the `name` tag back as a title, so the mux step sets the titles of kept audio tracks explicitly.

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
