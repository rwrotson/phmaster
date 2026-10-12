from pathlib import Path

import pytest

from mediagen import AudioSpec, make_media
from phmaster.services.errors import MediaError
from phmaster.services.media.probe import parse_probe, probe
from phmaster.services.media.tools import Tools


def test_probe_reads_audio_tracks(tools: Tools, tmp_path: Path) -> None:
    path = make_media(
        tmp_path / "movie.mkv",
        [
            AudioSpec(layout="5.1", language="rus", title="Dub"),
            AudioSpec(layout="stereo", language="und"),
        ],
        duration=1,
    )

    info = probe(tools, path)

    assert info.path == path
    assert "matroska" in info.format_name
    assert info.duration == pytest.approx(1, abs=0.1)
    assert info.stream_count == 3
    first, second = info.audio_tracks
    assert (first.stream_index, first.audio_index) == (1, 0)
    assert (first.codec, first.channels, first.layout) == ("aac", 6, "5.1")
    assert (first.language, first.title, first.sample_rate) == ("rus", "Dub", 48000)
    assert second.language is None
    assert second.audio_index == 1
    assert not info.has_generated_tracks


def test_probe_missing_file(tools: Tools, tmp_path: Path) -> None:
    with pytest.raises(MediaError, match="file not found"):
        probe(tools, tmp_path / "missing.mkv")


def test_probe_rejects_non_media(tools: Tools, tmp_path: Path) -> None:
    path = tmp_path / "notes.mkv"
    path.write_text("not a video", encoding="utf-8")
    with pytest.raises(MediaError, match="ffprobe"):
        probe(tools, path)


def test_probe_rejects_invalid_json(tools: Tools, tmp_path: Path) -> None:
    path = tmp_path / "x.mkv"
    path.write_bytes(b"")
    fake = Tools(ffmpeg=tools.ffmpeg, ffprobe="/bin/echo")
    with pytest.raises(MediaError, match="invalid JSON"):
        probe(fake, path)


def test_parse_probe_detects_generated_tracks_by_tag_or_title() -> None:
    data = {
        "format": {"format_name": "mov,mp4", "duration": "n/a"},
        "streams": [
            {"index": 0, "codec_type": "video"},
            {"index": 1, "codec_type": "audio", "channels": 2, "tags": {"PHMASTER": "night"}},
            {"index": 2, "codec_type": "audio", "channels": 2, "tags": {"name": "x · phmaster"}},
            {"index": 3, "codec_type": "audio", "channels": 1, "duration": "2.5"},
        ],
    }

    info = parse_probe(Path("a.mp4"), data)

    tagged, titled, plain = info.audio_tracks
    assert tagged.generated_by == "night"
    assert titled.is_generated
    assert titled.generated_by == ""
    assert titled.title == "x · phmaster"
    assert not plain.is_generated
    assert plain.duration == 2.5
    assert plain.layout == "mono"
    assert info.duration is None
    assert info.has_generated_tracks
