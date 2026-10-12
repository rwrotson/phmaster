import json

import typer
from rich.console import Console
from typer.testing import CliRunner

from cli_app.cli.context import AppContext, get_app_context
from cli_app.cli.errors import ServiceErrorGroup
from cli_app.config import Settings
from cli_app.services.errors import InvalidInputError, ServiceError
from cli_app.utils.output import OutputFormat

runner = CliRunner()


def make_app(output_format: OutputFormat | None = None) -> typer.Typer:
    app = typer.Typer(cls=ServiceErrorGroup)

    @app.callback()
    def root(ctx: typer.Context) -> None:
        if output_format is not None:
            ctx.obj = AppContext(
                settings=Settings(), console=Console(), output_format=output_format
            )

    @app.command()
    def fail() -> None:
        raise ServiceError("boom")

    @app.command()
    def invalid() -> None:
        raise InvalidInputError("bad input")

    @app.command()
    def context(ctx: typer.Context) -> None:
        get_app_context(ctx)

    return app


def test_service_error_without_context_is_reported_as_text() -> None:
    result = runner.invoke(make_app(), ["fail"])
    assert result.exit_code == 1
    assert result.stderr == "Error: boom\n"


def test_get_app_context_requires_root_callback() -> None:
    result = runner.invoke(make_app(), ["context"])
    assert isinstance(result.exception, RuntimeError)


def test_service_error_in_text_mode_uses_its_exit_code() -> None:
    result = runner.invoke(make_app(OutputFormat.text), ["invalid"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "Error: bad input\n"


def test_service_error_in_json_mode_is_reported_as_json() -> None:
    result = runner.invoke(make_app(OutputFormat.json), ["invalid"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {"type": "InvalidInputError", "message": "bad input"}
    }
