from typing import ClassVar


class ServiceError(Exception):
    """Base class for expected use-case failures reported by the CLI."""

    exit_code: ClassVar[int] = 1


class InvalidInputError(ServiceError):
    """The input cannot be processed."""

    # Matches Click's exit code for usage errors.
    exit_code = 2


class ToolNotFoundError(ServiceError):
    """A required external program (ffmpeg, ffprobe) is not installed."""

    exit_code = 3


class MediaError(ServiceError):
    """A media file cannot be read or does not contain what is needed."""

    exit_code = 4


class FfmpegError(ServiceError):
    """An ffmpeg or ffprobe process failed."""

    exit_code = 5

    def __init__(self, program: str, returncode: int, stderr: str) -> None:
        tail = "\n".join(stderr.strip().splitlines()[-10:])
        message = f"{program} exited with code {returncode}"
        super().__init__(f"{message}:\n{tail}" if tail else message)
        self.returncode = returncode
        self.stderr = stderr
