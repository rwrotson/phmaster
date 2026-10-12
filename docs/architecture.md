# Architecture

Commands are thin adapters: they read input, call a use case, and render its result. Use cases do not know about Typer, Rich, or configuration.

| Layer | Location | Responsibility | May import |
| --- | --- | --- | --- |
| Services | `phmaster/services/` | Use cases, DSP, ffmpeg integration, result types, and `ServiceError` subclasses | Services, the standard library, numpy, scipy |
| CLI | `phmaster/cli/` | Typer apps, options, `AppContext`, progress bar, error reporting, output | All layers |
| Configuration | `phmaster/config/` | `Settings` with defaults in code, loaded from `PHMASTER_*` and `.env` | Pydantic and the standard library |
| Utilities | `phmaster/utils/` | Console, logging, output, stdin, metadata helpers | Configuration and third-party libraries |
| Entry point | `phmaster/main.py` | Validate configuration, set up logging, run the app | All layers |

import-linter checks these boundaries with `uv run poe lint-imports`; the contracts are in `pyproject.toml`.

## Services

| Module | Responsibility |
| --- | --- |
| `services/media/tools.py` | Locate ffmpeg and ffprobe; run them and turn failures into errors |
| `services/media/probe.py` | Read tracks with ffprobe; recognise phmaster tracks by the `PHMASTER` tag (Matroska) or the title marker (MP4) |
| `services/media/layouts.py` | Channel order of ffmpeg's standard layouts |
| `services/media/commands.py` | Build decode, encode, and mux commands; choose the output container |
| `services/media/pcm.py` | Stream f32le PCM from and to ffmpeg processes |
| `services/dsp/loudness.py` | BS.1770 metering, gated loudness, LRA, reference level |
| `services/dsp/gain.py` | Gain planning and application |
| `services/dsp/presets.py` | Preset parameters |
| `services/pipeline.py` | Track selection, job planning, measure and render steps, `ProgressSink` |
| `services/normalize.py` | Process one file: skip rules, temporary files, mux, atomic replace |
| `services/batch.py` | Discover video files and process them, collecting failures |
| `services/analyze.py` | Measure tracks and estimate preset gains without writing |

`normalize_file()` probes the source, selects tracks, and expands them into jobs (track × layout × preset). Each (track, layout) pair is measured once and every preset is planned from that envelope. Each job is rendered into a temporary `.mka` in a `.phmaster-*` directory next to the output. The mux step writes a temporary output there. Without `--force`, a new output path is published with an atomic hard link that fails if another process created it; `--force` and replacement of the source use `os.replace`.

Services report progress through the `ProgressSink` protocol; the CLI implements it with a Rich progress bar on stderr.

The signal processing is described on the [Algorithm](algorithm.md) page.

## An invocation through the layers

1. `main()` loads `Settings`. Invalid configuration is printed to stderr and exits with code 2. It then configures logging from `settings.log`.
2. The root callback in `cli/app.py` stores an `AppContext` (settings, console, output format) in `ctx.obj`. Commands read it with `get_app_context(ctx)`.
3. A command combines its options with `settings.processing`, checks ffmpeg and ffprobe versions, and calls a use case in `services/`. Before measuring for processing, the use case checks the selected audio encoders.
4. The use case returns a result or raises a `ServiceError` subclass for an expected failure.
5. The command renders the result with `render_output()`: JSON on stdout for `--output-format json`, Rich text otherwise.

## Errors and exit codes

The root app uses `ServiceErrorGroup` (`cli/errors.py`). It catches `ServiceError` raised by any command, writes the message to stderr, and exits with the error's `exit_code`. With `--output-format json` the message is a JSON object, so stdout stays empty:

```json
{"error": {"type": "InvalidInputError", "message": "no video files found"}}
```

| Error | Exit code |
| --- | --- |
| `ServiceError` | 1 |
| `InvalidInputError` | 2, the same as Click usage errors |
| `ToolNotFoundError` | 3 |
| `MediaError` | 4 |
| `FfmpegError` | 5 |

`process` keeps going when a file fails; it reports each failure and exits with the code of the first one. Unexpected exceptions are not caught and keep their traceback.

## Adding a command

- Put the use case and its result type in `services/`. Raise a `ServiceError` subclass instead of calling `typer.Exit`.
- Add a command in `cli/commands/`: read `AppContext`, call the use case, render the result. Register its Typer app in `cli/app.py`; `add_typer()` without a name adds the command at the top level.
- Test the use case directly in `tests/services/` and the argument parsing, output, and exit codes with `CliRunner` in `tests/cli/`.
