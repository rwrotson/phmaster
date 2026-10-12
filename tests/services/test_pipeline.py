import gc
import weakref
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import phmaster.services.pipeline as pipeline_module
from phmaster.services.dsp.gain import GainPlan
from phmaster.services.dsp.loudness import LoudnessEnvelope
from phmaster.services.dsp.presets import PRESETS, Preset, PresetName
from phmaster.services.errors import InvalidInputError, MediaError
from phmaster.services.media.commands import Codec
from phmaster.services.media.probe import AudioTrack, MediaInfo, TrackOrigin
from phmaster.services.media.tools import Tools
from phmaster.services.pipeline import (
    CodecChoice,
    Job,
    Layout,
    NullProgress,
    ProgressSink,
    TrackFormat,
    TrackSelection,
    iter_plans,
    plan_jobs,
    select_tracks,
)

NIGHT = PRESETS[PresetName.night]
LIGHT = PRESETS[PresetName.light]


def track(
    index: int, layout: str | None = "5.1", channels: int = 6, **changes: object
) -> AudioTrack:
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
        origin=None,
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
    track(2, "stereo", 2, origin=TrackOrigin("night", "stereo", 1)),
    track(3, "stereo", 2, title="Phmaster commentary"),
)


def test_select_tracks_skips_generated() -> None:
    assert [t.audio_index for t in select_tracks(INFO, TrackSelection())] == [0, 1, 3]


def test_select_tracks_by_index_and_language() -> None:
    assert [t.audio_index for t in select_tracks(INFO, TrackSelection(indices=(1,)))] == [1]
    selection = TrackSelection(languages=("eng", "fra"))
    assert [t.audio_index for t in select_tracks(INFO, selection)] == [1]


def test_select_tracks_rejects_tracks_without_a_layout() -> None:
    info = media(track(0, "stereo", 2), track(1, None, 3))

    with pytest.raises(MediaError, match="a:1 has 3 channels and no channel layout"):
        select_tracks(info, TrackSelection())
    assert [t.audio_index for t in select_tracks(info, TrackSelection(indices=(0,)))] == [0]


def test_select_tracks_rejects_unknown_index() -> None:
    with pytest.raises(InvalidInputError, match=r"no audio track a:5 \(file has 4\)"):
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
        (track(0, "6.0", 6), Layout.keep, [("5.1", Codec.eac3, "640k")]),
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


def test_plan_jobs_renames_side_channels_for_opus() -> None:
    jobs = plan_jobs(
        [track(0, "5.1(side)", 6)], [NIGHT], TrackFormat(layout=Layout.keep, codec=CodecChoice.opus)
    )
    assert [(job.layout, job.codec, job.dialog_channel) for job in jobs] == [
        ("5.1", Codec.opus, False)
    ]


@pytest.mark.parametrize(
    ("source", "title"),
    [
        (track(0, title="Dub", language="rus"), "Dub · phmaster night (stereo, a:0)"),
        (track(0, language="rus"), "rus · phmaster night (stereo, a:0)"),
        (track(2), "Track 3 · phmaster night (stereo, a:2)"),
    ],
)
def test_job_title_and_tag(source: AudioTrack, title: str) -> None:
    (job,) = plan_jobs([source], [NIGHT], TrackFormat())
    assert job.title == title
    assert job.tag == f"night:stereo:{source.audio_index}"


def test_dialog_channel_only_when_downmix_loses_center() -> None:
    surround = plan_jobs([track(0)], [NIGHT], TrackFormat(layout=Layout.both))
    stereo = plan_jobs([track(0, "stereo", 2)], [NIGHT], TrackFormat())
    assert [job.dialog_channel for job in surround] == [True, False]
    assert not stereo[0].dialog_channel


def test_null_progress_accepts_updates() -> None:
    progress = NullProgress()
    progress.stage("step", 1.0)
    progress.advance(1.0)


def test_iter_plans_is_lazy_and_releases_finished_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    measured: list[tuple[int, str]] = []

    def fake_measure(
        tools: Tools, source: Path, job: Job, output: TrackFormat, progress: ProgressSink
    ) -> LoudnessEnvelope:
        measured.append((job.track.audio_index, job.layout))
        return LoudnessEnvelope(program=np.ones(4), dialog=None, peak=0.0)

    def fake_plan_gain(envelope: LoudnessEnvelope, preset: Preset) -> GainPlan:
        return GainPlan(gain=np.ones(4), reference=None, static_gain=0.0)

    monkeypatch.setattr(pipeline_module, "measure", fake_measure)
    monkeypatch.setattr(pipeline_module, "plan_gain", fake_plan_gain)
    jobs = plan_jobs([track(0), track(1)], [NIGHT, LIGHT], TrackFormat())
    planned = iter_plans(
        Tools("ffmpeg", "ffprobe"), Path("movie.mkv"), jobs, TrackFormat(), NullProgress()
    )
    assert measured == []

    first = next(planned)
    first_program = weakref.ref(first[1].program)
    first_gain = weakref.ref(first[2].gain)
    assert measured == [(0, "stereo")]
    del first

    second = next(planned)
    assert second[0].preset == LIGHT
    assert measured == [(0, "stereo")]
    assert first_gain() is None
    del second

    third = next(planned)
    gc.collect()
    assert measured == [(0, "stereo"), (1, "stereo")]
    assert first_program() is None
    assert third[0].track.audio_index == 1


def test_iter_plans_reuses_interleaved_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    measured: list[int] = []

    def fake_measure(
        tools: Tools, source: Path, job: Job, output: TrackFormat, progress: ProgressSink
    ) -> LoudnessEnvelope:
        measured.append(job.track.audio_index)
        return LoudnessEnvelope(program=np.ones(4), dialog=None, peak=0.0)

    monkeypatch.setattr(pipeline_module, "measure", fake_measure)
    jobs = plan_jobs([track(0), track(1)], [NIGHT, LIGHT], TrackFormat())
    jobs = [jobs[0], jobs[2], jobs[1], jobs[3]]

    planned = iter_plans(
        Tools("ffmpeg", "ffprobe"), Path("movie.mkv"), jobs, TrackFormat(), NullProgress()
    )

    assert [job for job, _, _ in planned] == jobs
    assert measured == [0, 1]
