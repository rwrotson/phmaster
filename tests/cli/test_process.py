import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mediagen import AudioSpec, ebur128, make_media, make_unknown_layout_wav
from phmaster.cli.app import app
from phmaster.cli.commands.process import resolve_format, resolve_presets, resolve_selection
from phmaster.config import ProcessingSettings
from phmaster.services.dsp.presets import PresetName
from phmaster.services.pipeline import CodecChoice, Layout

runner = CliRunner()


def test_process_writes_tracks_and_prints_table(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", [AudioSpec(layout="5.1")], duration=3)

    result = runner.invoke(
        app, ["process", str(source), "-p", "night", "-p", "light", "-l", "both"]
    )

    assert result.exit_code == 0, result.output
    assert "wrote movie.mkv → movie.phm.mkv" in result.stdout
    assert result.stdout.count("night") == 2
    assert (tmp_path / "movie.phm.mkv").is_file()


def test_process_reports_skipped_files(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)
    (tmp_path / "movie.phm.mkv").write_bytes(b"")

    result = runner.invoke(app, ["process", str(tmp_path)])

    assert result.exit_code == 0
    assert "skipped movie.mkv: output exists" in result.stdout
    assert source.is_file()


def test_process_json_dry_run(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    result = runner.invoke(
        app, ["-f", "json", "process", str(source), "--dry-run", "--codec", "flac", "--no-default"]
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["failures"] == []
    (entry,) = data["results"]
    assert entry["dry_run"] is True
    assert entry["output"].endswith("movie.phm.mkv")
    assert [t["codec"] for t in entry["tracks"]] == ["flac"]


def test_process_title_names_new_track(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    result = runner.invoke(
        app, ["-f", "json", "process", str(source), "--dry-run", "--title", "Late night"]
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["results"][0]["tracks"][0]["title"] == "Late night · phmaster night (stereo, a:0)"


def test_process_reports_failures_with_exit_code(tmp_path: Path) -> None:
    good = make_media(tmp_path / "good.mkv", duration=2)
    bad = tmp_path / "bad.mkv"
    bad.write_text("nope", encoding="utf-8")

    text = runner.invoke(app, ["process", str(bad), str(good), "-n"])
    data = runner.invoke(app, ["-f", "json", "process", str(bad), "-n"])

    assert text.exit_code == 4
    assert "Error: " in text.stderr
    assert "would write good.mkv" in text.stdout
    assert data.exit_code == 4
    assert json.loads(data.stdout)["failures"][0]["error"]["type"] == "MediaError"


def test_process_refuses_ambiguous_channel_layout(tmp_path: Path) -> None:
    # Only the third channel carries sound; guessing 2.1 would drop it from the stereo downmix.
    source = make_unknown_layout_wav(tmp_path / "audio.wav", [0.0, 0.0, 0.1])

    result = runner.invoke(app, ["process", str(source)])

    assert result.exit_code == 4
    assert "a:0 has 3 channels and no channel layout" in result.stderr
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audio.wav"]


def test_process_downmixes_six_channels_without_a_layout_as_5_1(tmp_path: Path) -> None:
    # Only the center carries sound, so a wrong channel guess would leave the downmix silent.
    source = make_unknown_layout_wav(tmp_path / "audio.wav", [0.0, 0.0, 0.1, 0.0, 0.0, 0.0])

    result = runner.invoke(app, ["--output-format", "json", "process", str(source)])

    assert result.exit_code == 0, result.stderr
    output = tmp_path / "audio.phm.mkv"
    assert ebur128(output, "a:1").integrated > -30


def test_process_rejects_empty_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["process", str(tmp_path)])
    assert result.exit_code == 2
    assert result.stderr == "Error: no video files found\n"


def test_process_requires_ffmpeg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PHMASTER_PROCESSING__FFMPEG", "no-such-ffmpeg")
    result = runner.invoke(app, ["process", str(tmp_path)])
    assert result.exit_code == 3
    assert "no-such-ffmpeg not found" in result.stderr


@pytest.mark.parametrize("value", ["13", "nan"])
def test_process_rejects_invalid_center_mix(tmp_path: Path, value: str) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)
    result = runner.invoke(app, ["process", str(source), "--dry-run", "--center-mix", value])
    assert result.exit_code == 2
    assert not (tmp_path / "movie.phm.mkv").exists()


def test_options_fall_back_to_settings() -> None:
    settings = ProcessingSettings(
        presets=["medium", "medium", "night"],
        layout="keep",
        codec="ac3",
        languages=["rus"],
        center_mix_db=-3,
    )
    assert [p.name for p in resolve_presets(None, settings)] == ["medium", "night"]
    assert [p.name for p in resolve_presets([PresetName.light], settings)] == ["light"]
    fmt = resolve_format(settings, None, None, None)
    assert (fmt.layout, fmt.codec, fmt.center_mix_db) == (Layout.keep, CodecChoice.ac3, -3)
    fmt = resolve_format(settings, Layout.stereo, CodecChoice.aac, 2.0)
    assert (fmt.layout, fmt.codec, fmt.center_mix_db) == (Layout.stereo, CodecChoice.aac, 2.0)
    assert resolve_selection(settings, None, None).languages == ("rus",)
    selection = resolve_selection(settings, [1], ["eng"])
    assert (selection.indices, selection.languages) == ((1,), ("eng",))
