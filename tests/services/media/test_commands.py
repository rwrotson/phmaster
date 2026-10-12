from pathlib import Path

import numpy as np
import pytest

from mediagen import AudioSpec, ffprobe_streams, make_media, packet_hashes
from phmaster.services.media.commands import (
    Codec,
    Container,
    DecodeSpec,
    EncodeSpec,
    NewTrack,
    choose_container,
    decode_command,
    encode_command,
    mux_command,
)
from phmaster.services.media.pcm import PcmWriter, read_pcm
from phmaster.services.media.tools import Tools, run_tool


def _decode(tools: Tools, spec: DecodeSpec) -> np.ndarray:
    with read_pcm(decode_command(tools, spec), spec.channels, 4800) as chunks:
        return np.concatenate(list(chunks))


def _encode(tools: Tools, path: Path, layout: str, codec: Codec, frames: np.ndarray) -> Path:
    spec = EncodeSpec(output=path, layout=layout, codec=codec, bitrate="192k", ceiling_db=-2.0)
    with PcmWriter(encode_command(tools, spec)) as writer:
        for start in range(0, len(frames), 4800):
            writer.write(frames[start : start + 4800])
    return path


def test_decode_keeps_layout_at_48k(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "a.mkv", [AudioSpec(layout="5.1")], duration=1)
    spec = DecodeSpec(source=source, audio_index=0, source_layout="5.1", target_layout="5.1")

    frames = _decode(tools, spec)

    assert frames.dtype == np.float32
    assert frames.shape[1] == 6
    assert abs(len(frames) - 48000) < 2048


def test_decode_downmix_appends_dialog_channel(tools: Tools, tmp_path: Path) -> None:
    source = make_media(tmp_path / "a.mkv", [AudioSpec(layout="5.1", burst=None)], duration=1)
    spec = DecodeSpec(
        source=source,
        audio_index=0,
        source_layout="5.1",
        target_layout="stereo",
        dialog_channel=True,
    )

    frames = _decode(tools, spec)

    assert spec.channels == 3
    assert frames.shape[1] == 3
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=0))
    assert rms[2] == pytest.approx(0.03 / np.sqrt(2), rel=0.1)
    assert np.all(rms[:2] > rms[2])


def test_decode_command_skips_rematrix_for_same_layout(tools: Tools) -> None:
    spec = DecodeSpec(
        source=Path("a.mkv"), audio_index=2, source_layout="stereo", target_layout="stereo"
    )
    graph = decode_command(tools, spec)[decode_command(tools, spec).index("-filter_complex") + 1]
    assert graph.startswith("[0:a:2]aresample=48000,aformat=")
    assert "ochl" not in graph


def test_encode_limits_peaks(tools: Tools, tmp_path: Path) -> None:
    t = np.arange(48000, dtype=np.float32) / 48000
    loud = np.stack([np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32)

    path = _encode(tools, tmp_path / "out.mka", "stereo", Codec.flac, loud)

    decoded = _decode(
        tools,
        DecodeSpec(source=path, audio_index=0, source_layout="stereo", target_layout="stereo"),
    )
    assert np.max(np.abs(decoded)) < 10 ** (-1.8 / 20)
    (stream,) = ffprobe_streams(path)
    assert stream["codec_name"] == "flac"


@pytest.mark.parametrize(
    ("codec", "layout", "channels"),
    [
        (Codec.aac, "stereo", 2),
        (Codec.eac3, "5.1", 6),
        (Codec.ac3, "5.1(side)", 6),
        (Codec.opus, "stereo", 2),
    ],
)
def test_encode_codecs(
    tools: Tools, tmp_path: Path, codec: Codec, layout: str, channels: int
) -> None:
    frames = np.zeros((9600, channels), dtype=np.float32)

    path = _encode(tools, tmp_path / "out.mka", layout, codec, frames)

    (stream,) = ffprobe_streams(path)
    assert stream["codec_name"] == codec.value
    assert stream["channels"] == channels


@pytest.mark.parametrize(
    ("name", "codecs", "expected"),
    [
        ("a.mkv", [Codec.aac], Container(".mkv", "matroska")),
        ("a.MP4", [Codec.aac, Codec.eac3], Container(".mp4", "mp4")),
        ("a.mov", [Codec.ac3], Container(".mov", "mov")),
        ("a.m4v", [Codec.aac], Container(".m4v", "mp4")),
        ("a.mp4", [Codec.opus], Container(".mkv", "matroska")),
        ("a.webm", [Codec.opus], Container(".webm", "webm")),
        ("a.webm", [Codec.aac], Container(".mkv", "matroska")),
        ("a.avi", [Codec.aac], Container(".mkv", "matroska")),
        ("a.mka", [Codec.aac], Container(".mkv", "matroska")),
        ("a.mk3d", [Codec.aac], Container(".mk3d", "matroska")),
    ],
)
def test_choose_container(name: str, codecs: list[Codec], expected: Container) -> None:
    assert choose_container(Path(name), codecs) == expected


@pytest.mark.parametrize(
    ("name", "subtitles", "container"),
    [
        ("movie.mkv", True, Container(".mkv", "matroska")),
        ("movie.mp4", True, Container(".mp4", "mp4")),
        ("movie.avi", False, Container(".mkv", "matroska")),
    ],
)
def test_mux_appends_tracks_and_copies_source(
    tools: Tools, tmp_path: Path, name: str, subtitles: bool, container: Container
) -> None:
    source = make_media(
        tmp_path / name,
        [AudioSpec(codec="mp3" if name.endswith(".avi") else "aac", language="eng")],
        duration=2,
        subtitles=subtitles,
    )
    track = _encode(
        tools, tmp_path / "new.mka", "stereo", Codec.aac, np.zeros((9600, 2), np.float32)
    )
    output = tmp_path / f"out{container.extension}"
    new = NewTrack(path=track, title="English · phmaster night", language="eng", tag="night")

    run_tool(
        mux_command(
            tools, source, [new], output, container, source_titles=["Original"], set_default=True
        )
    )

    streams = ffprobe_streams(output)
    audio = [s for s in streams if s["codec_type"] == "audio"]
    assert len(audio) == 2
    assert [s["disposition"]["default"] for s in audio] == [0, 1]
    tags = {k.lower(): v for k, v in audio[1]["tags"].items()}
    assert "phmaster" in (tags.get("title") or tags.get("name", ""))
    assert tags["language"] == "eng"
    assert (tags.get("phmaster") == "night") is container.is_matroska
    assert sum(s["codec_type"] == "subtitle" for s in streams) == int(subtitles)
    assert packet_hashes(output, "0:v:0") == packet_hashes(source, "0:v:0")
    assert packet_hashes(output, "0:a:0") == packet_hashes(source, "0:a:0")
    original = {k.lower(): v for k, v in audio[0]["tags"].items()}
    assert (original.get("title") or original.get("name")) == "Original"


@pytest.mark.parametrize(
    ("name", "container", "data_streams"),
    [
        # The MP4 muxer writes a new timecode track from the copied video stream's tag.
        ("movie.mp4", Container(".mp4", "mp4"), 1),
        ("movie.mov", Container(".mkv", "matroska"), 0),
        ("movie.mov", Container(".mov", "mov"), 1),
    ],
)
def test_mux_handles_timecode_data_streams(
    tools: Tools, tmp_path: Path, name: str, container: Container, data_streams: int
) -> None:
    source = make_media(tmp_path / name, duration=1, timecode=True)
    assert [s["codec_type"] for s in ffprobe_streams(source)].count("data") == 1
    track = _encode(
        tools, tmp_path / "new.mka", "stereo", Codec.aac, np.zeros((9600, 2), np.float32)
    )
    output = tmp_path / f"out{container.extension}"
    new = NewTrack(path=track, title="phmaster night", language=None, tag="night")

    run_tool(
        mux_command(
            tools, source, [new], output, container, source_titles=["Original"], set_default=True
        )
    )

    streams = [s["codec_type"] for s in ffprobe_streams(output)]
    assert streams.count("data") == data_streams
    assert streams.count("audio") == 2
    assert packet_hashes(output, "0:v:0") == packet_hashes(source, "0:v:0")


def test_mux_preserves_source_audio_dispositions(tools: Tools, tmp_path: Path) -> None:
    original = make_media(tmp_path / "original.mkv", duration=1)
    source = tmp_path / "source.mkv"
    run_tool(
        [
            tools.ffmpeg,
            "-v",
            "error",
            "-i",
            str(original),
            "-map",
            "0",
            "-c",
            "copy",
            "-disposition:a:0",
            "default+forced",
            str(source),
        ]
    )
    track = _encode(
        tools, tmp_path / "new.mka", "stereo", Codec.aac, np.zeros((9600, 2), np.float32)
    )
    output = tmp_path / "out.mkv"
    new = NewTrack(path=track, title="phmaster night", language=None, tag="night")

    run_tool(
        mux_command(
            tools,
            source,
            [new],
            output,
            Container(".mkv", "matroska"),
            source_titles=["Original"],
            set_default=True,
        )
    )

    audio = [stream for stream in ffprobe_streams(output) if stream["codec_type"] == "audio"]
    assert [
        (stream["disposition"]["default"], stream["disposition"]["forced"]) for stream in audio
    ] == [
        (0, 1),
        (1, 0),
    ]


def test_mux_command_options(tools: Tools) -> None:
    tracks = [
        NewTrack(path=Path("1.mka"), title="t1", language=None, tag="night"),
        NewTrack(path=Path("2.mka"), title="t2", language="rus", tag="light"),
    ]
    command = mux_command(
        tools,
        Path("in.ts"),
        tracks,
        Path("out.mp4"),
        Container(".mp4", "mp4"),
        source_titles=["Dub", None, "Original"],
        set_default=False,
    )
    assert command[command.index("-fflags") + 1] == "+genpts"
    assert command.count("-map") == 4
    assert command[command.index("-map") + 1] == "0"
    assert command[command.index("-map") + 3] == "-0:d"
    assert "-disposition:a" not in command
    assert command[command.index("-metadata:s:a:0") + 1] == "title=Dub"
    assert "-metadata:s:a:1" not in command
    assert command[command.index("-metadata:s:a:3") + 1] == "title=t1"
    assert "language=und" in command
    assert "language=rus" in command
    assert not any(arg.startswith("PHMASTER=") for arg in command)
    assert command[-3:] == ["-f", "mp4", "out.mp4"]
