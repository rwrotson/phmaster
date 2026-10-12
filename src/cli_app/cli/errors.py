from typing import Any

import typer
from typer.core import TyperGroup

from cli_app.cli.context import AppContext
from cli_app.services.errors import ServiceError
from cli_app.utils.output import OutputFormat, error_json


class ServiceErrorGroup(TyperGroup):
    """Report service errors on stderr and exit with their exit code."""

    # Typer passes its private vendored Click context, so the parameter is widened to Any.
    def invoke(self, ctx: Any) -> Any:  # noqa: ANN401
        """Run the command and convert service errors into exits."""
        try:
            return super().invoke(ctx)
        except ServiceError as error:
            app_context = ctx.find_object(AppContext)
            if app_context is not None and app_context.output_format == OutputFormat.json:
                error_json(type(error).__name__, str(error))
            else:
                typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(error.exit_code) from error
