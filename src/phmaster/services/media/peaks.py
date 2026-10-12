import re
import subprocess
from pathlib import Path

from phmaster.services.errors import FfmpegError
from phmaster.services.media.tools import Tools

_PEAK = re.compile(r"Summary:.*?^\s+Peak:\s+(-?[\d.]+|-inf)\s+dBFS", re.DOTALL | re.MULTILINE)


def true_peak(tools: Tools, path: Path) -> float | None:
    """Return the true peak of the first audio stream in dBTP, or None for silence."""
    command = [
        tools.ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise FfmpegError(Path(tools.ffmpeg).name, result.returncode, result.stderr)
    match = _PEAK.search(result.stderr)
    if match is None:
        raise FfmpegError(Path(tools.ffmpeg).name, 0, "ebur128 printed no true peak")
    return None if match[1] == "-inf" else float(match[1])
