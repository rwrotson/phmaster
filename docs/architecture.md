# Architecture

Commands are thin adapters: they read input, call a use case, and render its result. Use cases do not know about Typer, Rich, or configuration.

| Layer | Location | Responsibility | May import |
| --- | --- | --- | --- |
| Services | `cli_app/services/` | Use cases, their result types, and `ServiceError` subclasses | Services and the standard library |
| CLI | `cli_app/cli/` | Typer apps, options, `AppContext`, error reporting, output | All layers |
| Configuration | `cli_app/config/` | `Settings` with defaults in code, loaded from `CLI_APP_*` and `.env` | Pydantic and the standard library |
| Utilities | `cli_app/utils/` | Console, logging, output, stdin, metadata helpers | Configuration and third-party libraries |
| Entry point | `cli_app/main.py` | Validate configuration, set up logging, run the app | All layers |

import-linter checks these boundaries with `uv run poe lint-imports`; the contracts are in `pyproject.toml`.

## An invocation through the layers

1. `main()` loads `Settings`. Invalid configuration is printed to stderr and exits with code 2. It then configures logging from `settings.log`.
2. The root callback in `cli/app.py` stores an `AppContext` (settings, console, output format) in `ctx.obj`. Commands read it with `get_app_context(ctx)`.
3. A command resolves its input (arguments, options, piped stdin) and calls a use case in `services/`.
4. The use case returns a result or raises a `ServiceError` subclass for an expected failure.
5. The command renders the result with `render_output()`: JSON on stdout for `--output-format json`, Rich text otherwise.

## Errors and exit codes

The root app uses `ServiceErrorGroup` (`cli/errors.py`). It catches `ServiceError` raised by any command, writes the message to stderr, and exits with the error's `exit_code`. With `--output-format json` the message is a JSON object, so stdout stays empty:

```json
{"error": {"type": "InvalidInputError", "message": "argument required (or pipe input via stdin)"}}
```

| Error | Exit code |
| --- | --- |
| `ServiceError` | 1 |
| `InvalidInputError` | 2, the same as Click usage errors |

Add a subclass with its own `exit_code` for each new kind of expected failure. Unexpected exceptions are not caught and keep their traceback.

## Adding a command

- Put the use case and its result type in `services/`. Raise a `ServiceError` subclass instead of calling `typer.Exit`.
- Add a command in `cli/commands/`: read `AppContext`, call the use case, render the result. Register the group in `cli/app.py`.
- Test the use case directly in `tests/services/` and the argument parsing, output, and exit codes with `CliRunner` in `tests/cli/`.

`services/example.py` and `cli/commands/command.py` show this split.
