import numpy as np
import pytest

from phmaster.services.dsp.loudness import (
    BLOCK_SIZE,
    SAMPLE_RATE,
    BlockMeter,
    LoudnessEnvelope,
    channel_weights,
    integrated_loudness,
    loudness_range,
    reference_loudness,
    to_lufs,
    typical_level,
    windowed_power,
)


def sine(amplitude: float, seconds: float, frequency: float = 1000.0) -> np.ndarray:
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * frequency * t)


def measure(
    frames: np.ndarray, weights: list[float], dialog_index: int | None = None, chunk: int = 4800
) -> LoudnessEnvelope:
    meter = BlockMeter(weights, dialog_index)
    for start in range(0, len(frames), chunk):
        meter.feed(frames[start : start + chunk])
    return meter.finish()


def power_of(lufs: float) -> float:
    return float(10 ** ((lufs + 0.691) / 10))


def test_channel_weights() -> None:
    assert channel_weights(["FL", "FR", "FC", "LFE", "BL", "SR", "LFE2"]) == [
        1.0,
        1.0,
        1.0,
        0.0,
        1.41,
        1.41,
        0.0,
    ]


def test_reference_sine_measures_minus_23_lufs() -> None:
    envelope = measure(sine(0.1, 10)[:, None], [1.0])
    assert integrated_loudness(envelope.program) == pytest.approx(-23.0, abs=0.05)
    assert envelope.peak == pytest.approx(0.1, rel=1e-3)
    assert envelope.duration == pytest.approx(10.0)


def test_channels_sum_and_zero_weight_channels_are_ignored() -> None:
    tone = sine(0.1, 5)
    frames = np.stack([tone, tone, 10 * tone], axis=1)
    envelope = measure(frames, [1.0, 1.0, 0.0], dialog_index=2)
    assert integrated_loudness(envelope.program) == pytest.approx(-20.0, abs=0.05)
    assert envelope.peak == pytest.approx(0.1, rel=1e-3)
    assert envelope.dialog is not None
    assert integrated_loudness(envelope.dialog) == pytest.approx(-3.0, abs=0.05)


def test_chunking_does_not_change_the_envelope() -> None:
    frames = np.stack([sine(0.2, 1.003), sine(0.05, 1.003, 300)], axis=1)
    a = measure(frames, [1.0, 1.41], chunk=4800)
    b = measure(frames, [1.0, 1.41], chunk=777)
    assert len(a.program) == len(b.program) == -(-len(frames) // BLOCK_SIZE)
    np.testing.assert_allclose(a.program, b.program, rtol=1e-9)


def test_empty_input() -> None:
    meter = BlockMeter([1.0], dialog_index=0)
    meter.feed(np.zeros((0, 1)))
    envelope = meter.finish()
    assert len(envelope.program) == 0
    assert envelope.dialog is not None
    assert len(envelope.dialog) == 0
    assert integrated_loudness(envelope.program) is None
    assert reference_loudness(envelope) is None
    assert len(windowed_power(envelope.program, 3.0)) == 0
    assert BlockMeter([0.0]).finish().peak == 0.0


def test_silence_has_no_integrated_loudness() -> None:
    power = np.zeros(1000)
    assert integrated_loudness(power) is None
    assert loudness_range(power) == 0.0


def test_short_signal_uses_a_single_gating_block() -> None:
    power = np.full(20, power_of(-30))
    assert integrated_loudness(power) == pytest.approx(-30.0)


def test_relative_gate_ignores_quiet_passages() -> None:
    power = np.concatenate([np.full(1000, power_of(-20)), np.full(1000, power_of(-45))])
    assert integrated_loudness(power) == pytest.approx(-20.0, abs=0.1)


def test_loudness_range_of_two_levels() -> None:
    power = np.concatenate([np.full(2000, power_of(-30)), np.full(2000, power_of(-20))])
    assert loudness_range(power) == pytest.approx(10.0, abs=0.5)
    assert loudness_range(np.full(2000, power_of(-20))) == pytest.approx(0.0, abs=1e-6)


def test_to_lufs_floors_zero_power() -> None:
    assert float(to_lufs(0.0)) == pytest.approx(-120.691)


def test_reference_follows_dialogue_scenes() -> None:
    dialog_scene = np.full(1000, power_of(-28))
    action_scene = np.full(1000, power_of(-14))
    program = np.concatenate([dialog_scene, action_scene, action_scene, action_scene])
    dialog = np.concatenate([np.full(1000, power_of(-30)), np.full(3000, power_of(-60))])

    with_dialog = reference_loudness(LoudnessEnvelope(program=program, dialog=dialog, peak=0.0))
    without = reference_loudness(LoudnessEnvelope(program=program, dialog=None, peak=0.0))

    assert with_dialog == pytest.approx(-28.0, abs=0.1)
    assert without == pytest.approx(-14.0, abs=0.1)


@pytest.mark.parametrize(
    "dialog",
    [np.zeros(3000), np.concatenate([np.full(100, power_of(-20)), np.full(2900, power_of(-80))])],
)
def test_reference_falls_back_without_usable_dialogue(dialog: np.ndarray) -> None:
    program = np.full(3000, power_of(-25))
    envelope = LoudnessEnvelope(program=program, dialog=dialog, peak=0.0)
    assert reference_loudness(envelope) == pytest.approx(-25.0, abs=0.05)


def test_reference_falls_back_when_dialogue_blocks_are_silent_in_program() -> None:
    program = np.concatenate([np.zeros(1500), np.full(1500, power_of(-25))])
    dialog = np.concatenate([np.full(1500, power_of(-30)), np.full(1500, power_of(-80))])
    envelope = LoudnessEnvelope(program=program, dialog=dialog, peak=0.0)
    assert reference_loudness(envelope) == pytest.approx(-25.0, abs=0.05)


def test_reference_ignores_scenes_far_louder_than_dialogue() -> None:
    program = np.concatenate([np.full(2000, power_of(-31)), np.full(300, power_of(-8))])
    dialog = np.concatenate([np.full(2000, power_of(-35)), np.full(300, power_of(-12))])
    assert reference_loudness(
        LoudnessEnvelope(program=program, dialog=None, peak=0.0)
    ) == pytest.approx(-31.0, abs=0.1)
    assert reference_loudness(
        LoudnessEnvelope(program=program, dialog=dialog, peak=0.0)
    ) == pytest.approx(-31.0, abs=0.1)


def test_typical_level_of_silence_is_none() -> None:
    assert typical_level(np.zeros(10)) is None


@pytest.mark.parametrize(("quiet", "dialogue"), [(-42.0, -24.0), (-50.0, -35.0)])
def test_reference_without_dialogue_skips_long_quiet_stretches(
    quiet: float, dialogue: float
) -> None:
    # Ambience or pauses fill most of the track, so its median is not the dialogue level.
    cycle = [np.full(2000, power_of(quiet)), np.full(1000, power_of(dialogue))]
    program = np.concatenate(cycle * 4)
    envelope = LoudnessEnvelope(program=program, dialog=None, peak=0.0)
    assert reference_loudness(envelope) == pytest.approx(dialogue, abs=0.1)
