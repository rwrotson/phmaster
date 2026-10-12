from pathlib import Path

import pytest

from mediagen import make_media
from phmaster.services.batch import BatchResult, FileFailure, discover, process_files
from phmaster.services.dsp.presets import PRESETS, PresetName
from phmaster.services.errors import FfmpegError, InvalidInputError, MediaError
from phmaster.services.media.tools import find_tools
from phmaster.services.normalize import NormalizeRequest, NormalizeResult


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_discover_expands_directories(tmp_path: Path) -> None:
    movie = touch(tmp_path / "b.mkv")
    clip = touch(tmp_path / "a.MP4")
    touch(tmp_path / "b.phm.mkv")
    touch(tmp_path / ".hidden.mkv")
    touch(tmp_path / "notes.txt")
    nested = touch(tmp_path / "season" / "e01.avi")

    assert discover([tmp_path], recursive=False, suffix=".phm") == [clip, movie]
    assert discover([tmp_path], recursive=True, suffix=".phm") == [clip, movie, nested]


def test_discover_keeps_explicit_files_and_removes_duplicates(tmp_path: Path) -> None:
    other = touch(tmp_path / "x.dat")
    movie = touch(tmp_path / "m.mkv")
    assert discover([other, movie, tmp_path], recursive=False, suffix=".phm") == [other, movie]


def test_discover_rejects_missing_paths(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="path not found"):
        discover([tmp_path / "missing"], recursive=False, suffix=".phm")


def test_process_files_collects_results_and_failures(tmp_path: Path) -> None:
    good = make_media(tmp_path / "good.mkv", duration=2)
    bad = touch(tmp_path / "bad.mkv")
    seen: list[NormalizeResult | FileFailure] = []
    template = NormalizeRequest(source=good, presets=(PRESETS[PresetName.light],), dry_run=True)

    batch = process_files(find_tools(), [bad, good], template, on_result=seen.append)

    assert [r.source for r in batch.results] == [good]
    assert [f.path for f in batch.failures] == [bad]
    assert isinstance(batch.failures[0].error, MediaError)
    assert batch.exit_code == MediaError.exit_code
    assert seen == [batch.failures[0], batch.results[0]]


def test_batch_exit_code() -> None:
    assert BatchResult(results=(), failures=()).exit_code == 0
    failure = FileFailure(Path("a"), FfmpegError("ffmpeg", 1, ""))
    assert BatchResult(results=(), failures=(failure,)).exit_code == 5
