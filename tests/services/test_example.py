import pytest

from cli_app.services.errors import InvalidInputError
from cli_app.services.example import ExampleResult, run_example


def test_run_example_returns_result() -> None:
    assert run_example("hello", 3) == ExampleResult(argument="hello", option=3)


@pytest.mark.parametrize("argument", [None, ""])
def test_run_example_rejects_missing_argument(argument: str | None) -> None:
    with pytest.raises(InvalidInputError, match="argument required"):
        run_example(argument, None)


def test_invalid_input_uses_usage_exit_code() -> None:
    assert InvalidInputError.exit_code == 2
