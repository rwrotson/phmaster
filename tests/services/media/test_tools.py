import sys
from pathlib import Path

import pytest

from phmaster.services.errors import FfmpegError, MediaError, ToolNotFoundError
from phmaster.services.media.tools import find_tools, run_tool


def test_find_tools_resolves_absolute_paths() -> None:
    tools = find_tools()
    assert Path(tools.ffmpeg).is_absolute()
    assert Path(tools.ffprobe).is_absolute()


def test_find_tools_reports_missing_program() -> None:
    with pytest.raises(ToolNotFoundError, match="no-such-ffmpeg not found"):
        find_tools(ffmpeg="no-such-ffmpeg")


def test_run_tool_returns_stdout() -> None:
    assert run_tool([sys.executable, "-c", "print('ok')"]) == "ok\n"


def test_run_tool_raises_ffmpeg_error_with_stderr_tail() -> None:
    script = "import sys; sys.stderr.write('a\\nboom\\n'); sys.exit(3)"
    with pytest.raises(FfmpegError, match="exited with code 3:\na\nboom") as info:
        run_tool([sys.executable, "-c", script])
    assert info.value.returncode == 3


def test_run_tool_raises_given_error_with_last_line() -> None:
    script = "import sys; sys.stderr.write('a\\nboom\\n'); sys.exit(1)"
    with pytest.raises(MediaError, match=r": boom$"):
        run_tool([sys.executable, "-c", script], error=MediaError)


def test_run_tool_given_error_without_stderr() -> None:
    with pytest.raises(MediaError, match="unknown error"):
        run_tool([sys.executable, "-c", "raise SystemExit(1)"], error=MediaError)


def test_ffmpeg_error_without_stderr_has_short_message() -> None:
    assert str(FfmpegError("ffmpeg", 1, "  ")) == "ffmpeg exited with code 1"
