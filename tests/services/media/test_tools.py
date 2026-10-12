import sys
from pathlib import Path

import pytest

import phmaster.services.media.tools as tools_module
from phmaster.services.errors import FfmpegError, MediaError, ToolNotFoundError
from phmaster.services.media.tools import Tools, find_tools, require_encoders, run_tool


def test_find_tools_resolves_absolute_paths() -> None:
    tools = find_tools()
    assert Path(tools.ffmpeg).is_absolute()
    assert Path(tools.ffprobe).is_absolute()


def test_find_tools_reports_missing_program() -> None:
    with pytest.raises(ToolNotFoundError, match="no-such-ffmpeg not found"):
        find_tools(ffmpeg="no-such-ffmpeg")


GIT_BUILD = "N-113560-g1f47b2b4a6-20240301"


def fake_versions(
    monkeypatch: pytest.MonkeyPatch, ffmpeg_version: str, ffprobe_version: str, libavfilter: int
) -> None:
    def version(command: list[str]) -> str:
        name = Path(command[0]).name
        value = ffmpeg_version if name == "ffmpeg" else ffprobe_version
        return f"{name} version {value}\nlibavfilter    {libavfilter}.  4.100\n"

    monkeypatch.setattr(tools_module, "run_tool", version)


@pytest.mark.parametrize(
    ("ffmpeg_version", "ffprobe_version", "libavfilter"),
    [
        ("5.1", "6.0", 9),
        ("6.0", "5.1", 9),
        ("unknown", "6.0", 8),
        (GIT_BUILD, GIT_BUILD, 8),
    ],
)
def test_find_tools_rejects_old_or_unknown_versions(
    monkeypatch: pytest.MonkeyPatch, ffmpeg_version: str, ffprobe_version: str, libavfilter: int
) -> None:
    fake_versions(monkeypatch, ffmpeg_version, ffprobe_version, libavfilter)
    with pytest.raises(ToolNotFoundError, match=r"6\.0\+ required"):
        find_tools()


@pytest.mark.parametrize("build", [GIT_BUILD, "2024-03-04-git-e30369bc1c-full_build-www.gyan.dev"])
def test_find_tools_accepts_git_builds_by_library_version(
    monkeypatch: pytest.MonkeyPatch, build: str
) -> None:
    fake_versions(monkeypatch, build, build, 10)
    assert find_tools().ffmpeg.endswith("ffmpeg")


def test_require_encoders_reports_missing_audio_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    def encoders(command: list[str]) -> str:
        assert command[-1] == "-encoders"
        return " A..... aac                  AAC\n V..... libx264              H.264\n"

    monkeypatch.setattr(tools_module, "run_tool", encoders)
    tools = Tools(ffmpeg="fake-aac-only", ffprobe="fake-ffprobe")
    require_encoders(tools, ["aac"])
    with pytest.raises(ToolNotFoundError, match="eac3"):
        require_encoders(tools, ["aac", "eac3"])


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
