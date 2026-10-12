import sys
from collections.abc import Iterator


def is_stdin_piped() -> bool:
    """Return ``True`` when stdin is connected to a pipe rather than a TTY."""
    return not sys.stdin.isatty()


def read_stdin() -> str:
    """Read and return all content from stdin."""
    return sys.stdin.read()


def iter_stdin_lines() -> Iterator[str]:
    """Yield lines from stdin with trailing newlines stripped."""
    for line in sys.stdin:
        yield line.rstrip("\n")


def read_stdin_if_piped() -> str | None:
    """Return piped stdin without trailing line breaks; ``None`` when stdin is a TTY."""
    # Strip like shell command substitution so piped input matches the equivalent argument.
    return read_stdin().rstrip("\r\n") if is_stdin_piped() else None
