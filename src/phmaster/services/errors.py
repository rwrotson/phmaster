from typing import ClassVar


class ServiceError(Exception):
    """Base class for expected use-case failures reported by the CLI."""

    exit_code: ClassVar[int] = 1


class InvalidInputError(ServiceError):
    """The input cannot be processed."""

    # Matches Click's exit code for usage errors.
    exit_code = 2
