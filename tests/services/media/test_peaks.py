import subprocess
from pathlib import Path

import pytest

from mediagen import run
from phmaster.services.errors import FfmpegError
from phmaster.services.media.peaks import true_peak
from phmaster.services.media.tools import Tools, find_tools


@pytest.fixture
def tools() -> Tools:
    return find_tools()


def lavfi_flac(path: Path, source: str) -> Path:
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            source,
            "-c:a",
            "flac",
            str(path),
        ]
    )
    return path


def test_true_peak_of_a_half_scale_sine(tools: Tools, tmp_path: Path) -> None:
    path = lavfi_flac(tmp_path / "sine.mka", "aevalsrc=0.5*sin(2*PI*997*t):s=48000:d=2")
    assert true_peak(tools, path) == pytest.approx(-6.0, abs=0.1)


def test_true_peak_of_silence_is_none(tools: Tools, tmp_path: Path) -> None:
    path = lavfi_flac(tmp_path / "silence.mka", "anullsrc=r=48000:cl=stereo:d=1")
    assert true_peak(tools, path) is None


def test_true_peak_of_a_broken_file_raises(tools: Tools, tmp_path: Path) -> None:
    path = tmp_path / "broken.mka"
    path.write_bytes(b"not audio")
    with pytest.raises(FfmpegError):
        true_peak(tools, path)


def test_true_peak_requires_a_summary(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_summary(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", no_summary)
    with pytest.raises(FfmpegError, match="no true peak"):
        true_peak(tools, tmp_path / "any.mka")
