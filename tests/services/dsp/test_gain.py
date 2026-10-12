from dataclasses import replace

import numpy as np
import pytest

from phmaster.services.dsp.gain import GainApplier, plan_gain
from phmaster.services.dsp.loudness import BLOCK_SIZE, LoudnessEnvelope, to_lufs, windowed_power
from phmaster.services.dsp.presets import PRESETS, PresetName

NIGHT = PRESETS[PresetName.night]


def power_of(lufs: float) -> float:
    return float(10 ** ((lufs + 0.691) / 10))


def scenes(*parts: tuple[float, float]) -> LoudnessEnvelope:
    """Build an envelope from (seconds, LUFS) parts."""
    program = np.concatenate(
        [np.full(round(seconds * 100), power_of(level)) for seconds, level in parts]
    )
    return LoudnessEnvelope(program=program, dialog=None, peak=0.0)


EXPLOSION = scenes((20, -30), (2, -10), (20, -30))


def test_static_gain_moves_dialogue_to_target() -> None:
    plan = plan_gain(scenes((30, -30)), NIGHT)
    assert plan.reference == pytest.approx(-30.0, abs=0.05)
    assert plan.static_gain == pytest.approx(10.0, abs=0.05)
    np.testing.assert_allclose(plan.gain[500:2500], 10.0, atol=0.05)


def test_dialogue_reaches_target_when_ambience_dominates() -> None:
    envelope = scenes(*[(20, -42), (10, -24)] * 4)
    plan = plan_gain(envelope, NIGHT)
    output = to_lufs(windowed_power(envelope.program, 0.4)) + plan.gain
    assert plan.static_gain == pytest.approx(NIGHT.target + 24, abs=0.1)
    assert output[2300:2800].mean() == pytest.approx(NIGHT.target, abs=1.0)


def test_loud_scene_is_reduced_before_it_starts() -> None:
    plan = plan_gain(EXPLOSION, NIGHT)
    start = 2000
    assert plan.gain[start - 20] < plan.static_gain - 1
    assert plan.gain[start:2200].max() < plan.static_gain - 10


@pytest.mark.parametrize("name", list(PresetName))
def test_output_loudness_range_shrinks(name: PresetName) -> None:
    preset = PRESETS[name]
    plan = plan_gain(EXPLOSION, preset)
    output = to_lufs(windowed_power(EXPLOSION.program, 0.4)) + plan.gain
    peak_over_dialog = output[2000:2200].max() - output[500:1500].mean()
    assert peak_over_dialog < 20 - 4
    assert output[500:1500].mean() == pytest.approx(preset.target, abs=1.0)


@pytest.mark.parametrize("name", list(PresetName))
def test_dialogue_around_a_loud_moment_keeps_its_level(name: PresetName) -> None:
    preset = PRESETS[name]
    plan = plan_gain(EXPLOSION, preset)
    output = to_lufs(windowed_power(EXPLOSION.program, 0.4)) + plan.gain
    assert output[1700] == pytest.approx(preset.target, abs=1.0)
    assert output[2600] == pytest.approx(preset.target, abs=3.0)
    assert output[3000] == pytest.approx(preset.target, abs=1.0)


def test_long_quiet_scene_is_raised_but_short_dip_is_not() -> None:
    long_quiet = plan_gain(scenes((20, -25), (20, -37), (20, -25)), NIGHT)
    short_dip = plan_gain(scenes((20, -25), (2, -37), (20, -25)), NIGHT)
    assert long_quiet.gain[3000] > long_quiet.static_gain + 9
    assert short_dip.max_gain < short_dip.static_gain + 1


def test_stronger_presets_compress_more() -> None:
    spans = []
    for name in (PresetName.light, PresetName.medium, PresetName.night):
        plan = plan_gain(EXPLOSION, PRESETS[name])
        output = to_lufs(windowed_power(EXPLOSION.program, 0.4)) + plan.gain
        spans.append(output[2000:2200].max() - output[500:1500].mean())
    assert spans[0] > spans[1] > spans[2]


def test_gain_changes_smoothly() -> None:
    plan = plan_gain(EXPLOSION, NIGHT)
    assert np.abs(np.diff(plan.gain)).max() < 1.5


def test_quiet_scene_boost_is_capped() -> None:
    plan = plan_gain(scenes((30, -25), (30, -60 + 20), (30, -25)), NIGHT)
    assert plan.max_gain <= plan.static_gain + NIGHT.max_boost + 1e-6
    assert plan.min_gain < plan.max_gain


def test_quiet_scene_boost_fades_towards_silence() -> None:
    levels = [-46.0, -52.0, -58.0]
    plans = [plan_gain(scenes((20, -24), (15, level), (20, -24)), NIGHT) for level in levels]
    boosts = [float(np.median(plan.gain[2500:3000])) - plan.static_gain for plan in plans]
    outputs = [level + boost for level, boost in zip(levels, boosts, strict=True)]
    assert boosts[0] > boosts[1] > boosts[2]
    assert boosts[2] < 1.5
    assert outputs[0] > outputs[1] > outputs[2]


def test_silence_holds_surrounding_gain() -> None:
    plan = plan_gain(scenes((20, -30), (10, -90), (20, -30)), NIGHT)
    np.testing.assert_allclose(plan.gain, plan.static_gain, atol=0.3)


def test_silent_track_gets_unity_gain() -> None:
    plan = plan_gain(scenes((5, -100)), NIGHT)
    assert plan.reference is None
    assert plan.max_gain == plan.min_gain == 0.0


def test_mostly_silent_track_uses_static_gain() -> None:
    envelope = scenes((0.5, -30), (20, -90))
    plan = plan_gain(envelope, replace(NIGHT, smoothing=0.1))
    assert plan.reference == pytest.approx(-30.0, abs=2.0)
    assert np.ptp(plan.gain) < 0.2
    assert plan.max_gain == pytest.approx(plan.static_gain, abs=1.5)


def test_empty_envelope() -> None:
    plan = plan_gain(LoudnessEnvelope(program=np.zeros(0), dialog=None, peak=0.0), NIGHT)
    assert plan.min_gain == plan.max_gain == plan.static_gain == 0.0


def test_hard_knee_compression() -> None:
    soft = plan_gain(EXPLOSION, NIGHT)
    hard = plan_gain(EXPLOSION, replace(NIGHT, knee=0.0))
    assert hard.min_gain == pytest.approx(soft.min_gain, abs=1.0)


def test_gain_applier_interpolates_across_chunks() -> None:
    gain = np.array([0.0, 0.0, 20.0, 20.0])
    frames = np.ones((4 * BLOCK_SIZE, 3), dtype=np.float32)
    applier = GainApplier(gain)

    parts = [applier.apply(frames[i : i + 333], channels=2) for i in range(0, len(frames), 333)]
    out = np.concatenate(parts)

    assert out.shape == (len(frames), 2)
    assert out.dtype == np.float32
    assert out[0, 0] == pytest.approx(1.0)
    assert out[-1, 1] == pytest.approx(10.0)
    assert np.all(np.diff(out[:, 0]) >= 0)


def test_gain_applier_without_gain_is_unity() -> None:
    frames = np.full((10, 2), 0.5, dtype=np.float32)
    np.testing.assert_array_equal(GainApplier(np.zeros(0)).apply(frames), frames)
