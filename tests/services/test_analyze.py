from pathlib import Path

import pytest

from mediagen import AudioSpec, make_media
from phmaster.services.analyze import analyze_file
from phmaster.services.dsp.presets import PRESETS, PresetName
from phmaster.services.media.tools import find_tools
from phmaster.services.pipeline import Layout, TrackFormat, TrackSelection


def test_analyze_reports_each_track_layout_with_preset_estimates(tmp_path: Path) -> None:
    source = make_media(
        tmp_path / "movie.mkv",
        [AudioSpec(layout="5.1", level=0.02, burst=(4.0, 5.0)), AudioSpec()],
        duration=8,
    )
    presets = (PRESETS[PresetName.night], PRESETS[PresetName.light])

    result = analyze_file(
        find_tools(),
        source,
        presets=presets,
        track_format=TrackFormat(layout=Layout.both),
        selection=TrackSelection(indices=(0,)),
    )

    assert len(result.info.audio_tracks) == 2
    assert [(r.audio_index, r.layout) for r in result.reports] == [(0, "stereo"), (0, "5.1")]
    report = result.reports[0]
    assert report.integrated is not None
    assert report.reference is not None
    assert report.reference < report.integrated - 5
    assert report.loudness_range > 10
    assert -12 < report.peak_db < 0
    night, light = report.estimates
    assert (night.preset, light.preset) == ("night", "light")
    assert night.min_gain < light.min_gain
    assert night.static_gain == pytest.approx(night.max_gain, abs=2)
