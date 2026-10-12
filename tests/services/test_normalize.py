from pathlib import Path

import pytest

import phmaster.services.normalize as normalize_module
from mediagen import AudioSpec, ebur128, ffprobe_streams, make_media, packet_hashes
from phmaster.services.dsp.presets import PRESETS, PresetName
from phmaster.services.errors import FfmpegError
from phmaster.services.media.commands import Container
from phmaster.services.media.tools import Tools, find_tools
from phmaster.services.normalize import NormalizeRequest, normalize_file, output_path
from phmaster.services.pipeline import CodecChoice, Layout, TrackFormat, TrackSelection

NIGHT = PRESETS[PresetName.night]
LIGHT = PRESETS[PresetName.light]
# A quiet scene with a burst 20 dB louder, long enough for the gain planner to act.
SCENE = AudioSpec(layout="5.1", language="rus", title="Dub", level=0.02, burst=(6.0, 8.0))


class RecordingProgress:
    def __init__(self) -> None:
        self.stages: list[str] = []
        self.seconds = 0.0

    def stage(self, description: str, total: float | None) -> None:
        self.stages.append(description)

    def advance(self, seconds: float) -> None:
        self.seconds += seconds


@pytest.fixture
def tools() -> Tools:
    return find_tools()


def audio_streams(path: Path) -> list[dict[str, object]]:
    return [s for s in ffprobe_streams(path) if s["codec_type"] == "audio"]


def test_normalize_appends_tracks_and_tames_the_burst(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", [SCENE], duration=14, subtitles=True)
    progress = RecordingProgress()

    result = normalize_file(
        tools,
        NormalizeRequest(
            source=source, presets=(NIGHT, LIGHT), track_format=TrackFormat(layout=Layout.both)
        ),
        progress,
    )

    assert result.output == tmp_path / "movie.phm.mkv"
    assert [(t.preset, t.layout, t.codec) for t in result.tracks] == [
        ("night", "stereo", "aac"),
        ("light", "stereo", "aac"),
        ("night", "5.1", "eac3"),
        ("light", "5.1", "eac3"),
    ]
    assert all(t.reference == pytest.approx(-30.5, abs=1.5) for t in result.tracks)
    audio = audio_streams(result.output)
    assert len(audio) == 5
    assert [s["disposition"]["default"] for s in audio] == [0, 1, 0, 0, 0]  # type: ignore[index]
    assert packet_hashes(result.output, "0:a:0") == packet_hashes(source, "0:a:0")
    assert packet_hashes(result.output, "0:s:0") == packet_hashes(source, "0:s:0")
    source_lra = ebur128(source, "0:a:0").loudness_range
    night = ebur128(result.output, "0:a:1")
    assert night.loudness_range < source_lra - 8
    assert night.true_peak <= NIGHT.ceiling + 0.5
    assert progress.stages[0].startswith("Measuring Dub (stereo)")
    assert progress.stages[-1] == "Writing movie.phm.mkv"
    assert progress.seconds == pytest.approx(14 * 6, rel=0.05)
    assert not list(tmp_path.glob(".phmaster-*"))


def test_flac_output_respects_the_true_peak_ceiling(tools: Tools, tmp_path: Path) -> None:
    source = make_media(
        tmp_path / "movie.mkv", [AudioSpec(level=0.3, burst=(1.0, 2.0))], duration=4
    )
    request = NormalizeRequest(
        source=source, presets=(LIGHT,), track_format=TrackFormat(codec=CodecChoice.flac)
    )

    result = normalize_file(tools, request)

    assert ebur128(result.output, "0:a:1").true_peak <= LIGHT.ceiling + 0.2


def test_mp4_stays_mp4_and_marks_tracks_by_title(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "clip.mp4", [AudioSpec(language="eng")], duration=3)

    result = normalize_file(
        tools, NormalizeRequest(source=source, presets=(NIGHT,), set_default=False)
    )

    assert result.output == tmp_path / "clip.phm.mp4"
    assert [s["disposition"]["default"] for s in audio_streams(result.output)] == [1, 0]  # type: ignore[index]
    rerun = normalize_file(tools, NormalizeRequest(source=result.output, presets=(NIGHT,)))
    assert rerun.skipped == "already contains phmaster tracks"


def test_skips_existing_output_unless_forced(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=3)
    request = NormalizeRequest(source=source, presets=(NIGHT,))
    first = normalize_file(tools, request)

    skipped = normalize_file(tools, request)
    forced = normalize_file(tools, NormalizeRequest(source=source, presets=(LIGHT,), force=True))

    assert skipped.skipped == "output exists: movie.phm.mkv"
    assert skipped.tracks[0].min_gain is None
    assert forced.output == first.output
    assert forced.skipped is None
    assert len(audio_streams(forced.output)) == 2


def test_dry_run_writes_nothing(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    result = normalize_file(tools, NormalizeRequest(source=source, presets=(NIGHT,), dry_run=True))

    assert result.dry_run
    assert len(result.tracks) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["movie.mkv"]


def test_in_place_replaces_the_source(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    result = normalize_file(tools, NormalizeRequest(source=source, presets=(NIGHT,), in_place=True))

    assert result.output == source
    assert len(audio_streams(source)) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["movie.mkv"]


def test_in_place_conversion_removes_the_old_file(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "old.avi", [AudioSpec(codec="mp3")], duration=2)

    result = normalize_file(tools, NormalizeRequest(source=source, presets=(NIGHT,), in_place=True))

    assert result.output == tmp_path / "old.mkv"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["old.mkv"]


def test_in_place_does_not_overwrite_another_file(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "old.avi", [AudioSpec(codec="mp3")], duration=2)
    (tmp_path / "old.mkv").write_bytes(b"keep me")

    result = normalize_file(tools, NormalizeRequest(source=source, presets=(NIGHT,), in_place=True))

    assert result.skipped == "output exists: old.mkv"
    assert (tmp_path / "old.mkv").read_bytes() == b"keep me"


def test_failed_mux_leaves_no_files(
    tools: Tools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    def broken(command: list[str]) -> str:
        raise FfmpegError("ffmpeg", 1, "mux failed")

    monkeypatch.setattr(normalize_module, "run_tool", broken)
    with pytest.raises(FfmpegError, match="mux failed"):
        normalize_file(tools, NormalizeRequest(source=source, presets=(NIGHT,)))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["movie.mkv"]


def test_selection_limits_tracks(tools: Tools, tmp_path: Path) -> None:
    source = make_media(
        tmp_path / "movie.mkv", [AudioSpec(language="rus"), AudioSpec(language="eng")], duration=2
    )
    request = NormalizeRequest(
        source=source, presets=(NIGHT,), selection=TrackSelection(languages=("eng",)), dry_run=True
    )

    result = normalize_file(tools, request)

    assert [t.source_index for t in result.tracks] == [1]


@pytest.mark.parametrize(
    ("in_place", "expected"), [(False, "a/movie.phm.mp4"), (True, "a/movie.mp4")]
)
def test_output_path(in_place: bool, expected: str) -> None:
    container = Container(".mp4", "mp4")
    assert output_path(Path("a/movie.mp4"), container, ".phm", in_place=in_place) == Path(expected)
