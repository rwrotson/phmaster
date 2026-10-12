from dataclasses import replace
from pathlib import Path

import pytest

from phmaster.services.dsp.presets import PRESETS, PresetName
from phmaster.services.errors import InvalidInputError, MediaError
from phmaster.services.media.commands import Codec
from phmaster.services.media.probe import AudioTrack, MediaInfo
from phmaster.services.pipeline import (
    CodecChoice,
    Layout,
    NullProgress,
    TrackFormat,
    TrackSelection,
    plan_jobs,
    select_tracks,
)

NIGHT = PRESETS[PresetName.night]
LIGHT = PRESETS[PresetName.light]


def track(index: int, layout: str = "5.1", channels: int = 6, **changes: object) -> AudioTrack:
    base = AudioTrack(
        stream_index=index + 1,
        audio_index=index,
        codec="ac3",
        channels=channels,
        layout=layout,
        sample_rate=48000,
        language=None,
        title=None,
        duration=10.0,
        generated_by=None,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def media(*tracks: AudioTrack) -> MediaInfo:
    return MediaInfo(
        path=Path("movie.mkv"),
        format_name="matroska",
        duration=10.0,
        stream_count=len(tracks) + 1,
        audio_tracks=tracks,
    )


INFO = media(
    track(0, language="rus"),
    track(1, "stereo", 2, language="ENG"),
    track(2, "stereo", 2, generated_by="night"),
)


def test_select_tracks_skips_generated() -> None:
    assert [t.audio_index for t in select_tracks(INFO, TrackSelection())] == [0, 1]


def test_select_tracks_by_index_and_language() -> None:
    assert [t.audio_index for t in select_tracks(INFO, TrackSelection(indices=(1,)))] == [1]
    selection = TrackSelection(languages=("eng", "fra"))
    assert [t.audio_index for t in select_tracks(INFO, selection)] == [1]


def test_select_tracks_rejects_unknown_index() -> None:
    with pytest.raises(InvalidInputError, match=r"no audio track a:5 \(file has 3\)"):
        select_tracks(INFO, TrackSelection(indices=(5,)))


@pytest.mark.parametrize(
    "selection", [TrackSelection(indices=(2,)), TrackSelection(languages=("jpn",))]
)
def test_select_tracks_requires_a_match(selection: TrackSelection) -> None:
    with pytest.raises(MediaError, match="no audio tracks to process"):
        select_tracks(INFO, selection)


@pytest.mark.parametrize(
    ("source", "layout", "expected"),
    [
        (track(0), Layout.stereo, [("stereo", Codec.aac, "256k")]),
        (track(0), Layout.keep, [("5.1", Codec.eac3, "640k")]),
        (track(0), Layout.both, [("stereo", Codec.aac, "256k"), ("5.1", Codec.eac3, "640k")]),
        (track(0, "7.1", 8), Layout.keep, [("5.1", Codec.eac3, "640k")]),
        (track(0, "stereo", 2), Layout.both, [("stereo", Codec.aac, "256k")]),
        (track(0, "mono", 1), Layout.keep, [("mono", Codec.aac, "256k")]),
    ],
)
def test_plan_jobs_layouts_and_auto_codec(
    source: AudioTrack, layout: Layout, expected: list[tuple[str, Codec, str]]
) -> None:
    jobs = plan_jobs([source], [NIGHT], TrackFormat(layout=layout))
    assert [(job.layout, job.codec, job.bitrate) for job in jobs] == expected


def test_plan_jobs_expands_presets_and_honours_codec() -> None:
    jobs = plan_jobs(
        [track(0)], [NIGHT, LIGHT], TrackFormat(layout=Layout.both, codec=CodecChoice.opus)
    )
    assert [(job.preset.name, job.layout, job.codec) for job in jobs] == [
        ("night", "stereo", Codec.opus),
        ("light", "stereo", Codec.opus),
        ("night", "5.1", Codec.opus),
        ("light", "5.1", Codec.opus),
    ]


@pytest.mark.parametrize(
    ("source", "title"),
    [
        (track(0, title="Dub", language="rus"), "Dub · phmaster night (stereo)"),
        (track(0, language="rus"), "rus · phmaster night (stereo)"),
        (track(2), "Track 3 · phmaster night (stereo)"),
    ],
)
def test_job_title_and_tag(source: AudioTrack, title: str) -> None:
    (job,) = plan_jobs([source], [NIGHT], TrackFormat())
    assert job.title == title
    assert job.tag == "night:stereo"


def test_dialog_channel_only_when_downmix_loses_center() -> None:
    surround = plan_jobs([track(0)], [NIGHT], TrackFormat(layout=Layout.both))
    stereo = plan_jobs([track(0, "stereo", 2)], [NIGHT], TrackFormat())
    assert [job.dialog_channel for job in surround] == [True, False]
    assert not stereo[0].dialog_channel


def test_null_progress_accepts_updates() -> None:
    progress = NullProgress()
    progress.stage("step", 1.0)
    progress.advance(1.0)
