import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from phmaster.services.errors import FfmpegError, MediaError, ToolNotFoundError

# ffprobe reports MP4 track titles per stream only since ffmpeg 8.1.
MIN_FFMPEG = (8, 1)
# libavformat shipped with ffmpeg 8.1; git builds report only library versions.
MIN_LIBAVFORMAT = (62, 12)
_ENCODER_FLAGS_LENGTH = 6
_MIN_ENCODER_FIELDS = 2
_VERSION = re.compile(r"\bversion\s+n?(\d+)\.(\d+)")
_LIBAVFORMAT = re.compile(r"^libavformat\s+(\d+)\.\s*(\d+)\.", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Tools:
    """Resolved paths of the ffmpeg and ffprobe executables."""

    ffmpeg: str
    ffprobe: str


def find_tools(ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> Tools:
    """Locate ffmpeg and ffprobe on PATH or at the given paths."""
    resolved: list[str] = []
    for name, program in ((ffmpeg, "ffmpeg"), (ffprobe, "ffprobe")):
        path = shutil.which(name)
        if path is None:
            raise ToolNotFoundError(f"{name} not found; install ffmpeg and make sure it is on PATH")
        resolved.append(path)
        _check_version(path, program)
    return Tools(ffmpeg=resolved[0], ffprobe=resolved[1])


def require_encoders(tools: Tools, names: Iterable[str]) -> None:
    """Require the selected audio encoders before measuring media."""
    missing = set(names) - _available_audio_encoders(tools.ffmpeg)
    if missing:
        raise ToolNotFoundError(
            f"ffmpeg lacks required audio encoder(s): {', '.join(sorted(missing))}"
        )


def _check_version(path: str, program: str) -> None:
    try:
        output = run_tool([path, "-version"])
    except FfmpegError as error:
        raise ToolNotFoundError(f"{Path(path).name} version check failed: {error}") from error
    first_line = output.splitlines()[0] if output else ""
    if not first_line.startswith(f"{program} version "):
        supported = False
    elif release := _VERSION.search(first_line):
        supported = (int(release.group(1)), int(release.group(2))) >= MIN_FFMPEG
    else:
        library = _LIBAVFORMAT.search(output)
        supported = library is not None and (
            (int(library.group(1)), int(library.group(2))) >= MIN_LIBAVFORMAT
        )
    if not supported:
        raise ToolNotFoundError(f"{program} 8.1+ required; reported: {first_line or 'unknown'}")


@lru_cache(maxsize=16)
def _available_audio_encoders(ffmpeg: str) -> frozenset[str]:
    try:
        output = run_tool([ffmpeg, "-hide_banner", "-encoders"])
    except FfmpegError as error:
        raise ToolNotFoundError(f"ffmpeg encoder check failed: {error}") from error
    names: set[str] = set()
    for line in output.splitlines():
        fields = line.split()
        if (
            len(fields) >= _MIN_ENCODER_FIELDS
            and len(fields[0]) == _ENCODER_FLAGS_LENGTH
            and fields[0].startswith("A")
            and fields[1] != "="
        ):
            names.add(fields[1])
    return frozenset(names)


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
