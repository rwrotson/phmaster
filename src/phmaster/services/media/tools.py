import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from phmaster.services.errors import FfmpegError, MediaError, ToolNotFoundError


@dataclass(frozen=True, slots=True)
class Tools:
    """Resolved paths of the ffmpeg and ffprobe executables."""

    ffmpeg: str
    ffprobe: str


def find_tools(ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> Tools:
    """Locate ffmpeg and ffprobe on PATH or at the given paths."""
    resolved: list[str] = []
    for name in (ffmpeg, ffprobe):
        path = shutil.which(name)
        if path is None:
            raise ToolNotFoundError(f"{name} not found; install ffmpeg and make sure it is on PATH")
        resolved.append(path)
    return Tools(ffmpeg=resolved[0], ffprobe=resolved[1])


def run_tool(command: list[str], *, error: type[MediaError] | None = None) -> str:
    """Run an ffmpeg or ffprobe command and return its stdout.

    A failure raises FfmpegError, or the given MediaError subclass with ffmpeg's message.
    """
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        if error is not None:
            message = result.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise error(f"{Path(command[0]).name}: {message[0]}")
        raise FfmpegError(Path(command[0]).name, result.returncode, result.stderr)
    return result.stdout
