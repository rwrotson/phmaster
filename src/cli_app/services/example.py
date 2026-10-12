from dataclasses import dataclass

from cli_app.services.errors import InvalidInputError


@dataclass(frozen=True, slots=True)
class ExampleResult:
    """Validated input of the example command."""

    argument: str
    option: int | None


def run_example(argument: str | None, option: int | None) -> ExampleResult:
    """Validate the example input and return it as a result."""
    if not argument:
        raise InvalidInputError("argument required (or pipe input via stdin)")
    return ExampleResult(argument=argument, option=option)
