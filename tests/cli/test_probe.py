import json
from pathlib import Path

from typer.testing import CliRunner

from mediagen import AudioSpec, make_media
from phmaster.cli.app import app

runner = CliRunner()


def test_probe_lists_tracks(tmp_path: Path) -> None:
    source = make_media(
        tmp_path / "movie.mkv",
        [AudioSpec(layout="5.1", language="rus", title="Dub"), AudioSpec()],
        duration=2,
    )

    result = runner.invoke(app, ["probe", str(source)])

    assert result.exit_code == 0
    assert "a:0" in result.stdout
    assert "5.1" in result.stdout
    assert "Dub" in result.stdout
    assert "0:00:02" in result.stdout


def test_probe_json(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", duration=2)

    result = runner.invoke(app, ["-f", "json", "probe", str(source)])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["audio_tracks"][0]["layout"] == "stereo"


def test_probe_loudness_text_and_json(tmp_path: Path) -> None:
    source = make_media(tmp_path / "movie.mkv", [AudioSpec(burst=(1.0, 2.0))], duration=4)

    text = runner.invoke(app, ["probe", str(source), "-L", "-p", "night", "-p", "light"])
    data = runner.invoke(app, ["-f", "json", "probe", str(source), "--loudness"])

    assert text.exit_code == 0
    assert "LUFS" in text.stdout
    assert "night" in text.stdout
    assert "light" in text.stdout
    report = json.loads(data.stdout)["reports"][0]
    assert report["layout"] == "stereo"
    assert [e["preset"] for e in report["estimates"]] == ["night"]


def test_probe_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["probe", str(tmp_path / "missing.mkv")])
    assert result.exit_code == 4
    assert "file not found" in result.stderr
