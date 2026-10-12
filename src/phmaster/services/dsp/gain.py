from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d, maximum_filter1d, minimum_filter1d, uniform_filter1d

from phmaster.services.dsp.loudness import (
    BLOCK_SECONDS,
    BLOCK_SIZE,
    MOMENTARY_SECONDS,
    SHORT_TERM_SECONDS,
    LoudnessEnvelope,
    Signal,
    reference_loudness,
    to_lufs,
    windowed_power,
)
from phmaster.services.dsp.presets import Preset

# Scenes quieter than this (absolute, or relative to the dialogue level) keep the surrounding
# gain instead of being raised, so room tone and noise floors are not pumped up.
SILENCE_FLOOR = -60.0
SILENCE_RELATIVE = -35.0
# Quieter passages are raised only when they last longer than this, so fades and short
# pauses keep the gain of the scene around them.
BOOST_HOLD_SECONDS = 4.0


@dataclass(frozen=True, slots=True)
class GainPlan:
    """Gain in dB per 10 ms block, with the levels it was derived from."""

    gain: Signal
    reference: float | None
    static_gain: float

    @property
    def min_gain(self) -> float:
        """Lowest planned gain in dB."""
        return float(self.gain.min()) if len(self.gain) else self.static_gain

    @property
    def max_gain(self) -> float:
        """Highest planned gain in dB."""
        return float(self.gain.max()) if len(self.gain) else self.static_gain


def plan_gain(envelope: LoudnessEnvelope, preset: Preset) -> GainPlan:
    """Plan a smooth, non-causal gain curve that keeps loudness near the dialogue level."""
    reference = reference_loudness(envelope)
    if reference is None:
        return GainPlan(gain=np.zeros(len(envelope.program)), reference=None, static_gain=0.0)
    static_gain = preset.target - reference
    slow = _slow_gain(envelope.program, reference, static_gain, preset)
    fast = _compression(envelope.program, slow, preset)
    gain = _lookahead_smooth(slow + fast, preset.lookahead)
    gain = _release(gain, preset.release)
    return GainPlan(gain=gain, reference=reference, static_gain=static_gain)


def _slow_gain(power: Signal, reference: float, static_gain: float, preset: Preset) -> Signal:
    short_term = _bridge_silence(power, reference)
    if short_term is None:
        return np.full(len(power), static_gain)
    held = maximum_filter1d(short_term, round(BOOST_HOLD_SECONDS / BLOCK_SECONDS), mode="nearest")
    deviation = np.clip(preset.strength * (reference - held), -preset.max_cut, preset.max_boost)
    sigma = preset.smoothing / BLOCK_SECONDS
    return np.asarray(
        gaussian_filter1d(static_gain + deviation, sigma, mode="nearest"), dtype=np.float64
    )


def _bridge_silence(power: Signal, reference: float) -> Signal | None:
    """Return short-term loudness with silent stretches interpolated from their neighbours.

    Silence is detected on momentary loudness and widened by half the short-term window, so
    windows that only partly cover silence do not look like quiet scenes. None means the whole
    track is silent.
    """
    momentary = to_lufs(windowed_power(power, MOMENTARY_SECONDS))
    silent = momentary < max(SILENCE_FLOOR, reference + SILENCE_RELATIVE)
    margin = round(SHORT_TERM_SECONDS / BLOCK_SECONDS) | 1
    silent = maximum_filter1d(silent, margin, mode="nearest")
    if silent.all():
        return None
    short_term = to_lufs(windowed_power(power, SHORT_TERM_SECONDS))
    if silent.any():
        index = np.arange(len(power))
        short_term[silent] = np.interp(index[silent], index[~silent], short_term[~silent])
    return short_term


def _compression(power: Signal, slow: Signal, preset: Preset) -> Signal:
    momentary = to_lufs(windowed_power(power, MOMENTARY_SECONDS)) + slow
    over = momentary - (preset.target + preset.threshold)
    half_knee = preset.knee / 2
    slope = 1 - 1 / preset.ratio
    in_knee = np.clip(over + half_knee, 0, preset.knee)
    reduction = np.where(
        over > half_knee,
        over * slope,
        slope * in_knee**2 / (2 * preset.knee) if preset.knee > 0 else 0.0,
    )
    return np.asarray(-reduction, dtype=np.float64)


def _lookahead_smooth(gain: Signal, lookahead: float) -> Signal:
    """Lower the gain ahead of every dip so that smoothing never overshoots it.

    A minimum over a centered window followed by a moving average of the same width keeps
    every value at or below the original curve at the dip itself.
    """
    if len(gain) == 0:
        return gain
    size = 2 * max(1, round(lookahead / BLOCK_SECONDS)) + 1
    floor = minimum_filter1d(gain, size, mode="nearest")
    return np.asarray(uniform_filter1d(floor, size, mode="nearest"), dtype=np.float64)


def _release(gain: Signal, release: float) -> Signal:
    """Follow falling gain at once and rising gain with a one-pole release."""
    coefficient = float(np.exp(-BLOCK_SECONDS / release))
    out = gain.copy()
    for index in range(1, len(out)):
        previous = out[index - 1]
        if out[index] > previous:
            out[index] = previous + (1 - coefficient) * (out[index] - previous)
    return out


class GainApplier:
    """Apply a block gain curve to streamed samples with linear interpolation in dB."""

    def __init__(self, gain: Signal) -> None:
        self._gain = gain
        self._centers = (np.arange(len(gain)) + 0.5) * BLOCK_SIZE
        self._position = 0

    def apply(
        self, frames: NDArray[np.floating], channels: int | None = None
    ) -> NDArray[np.float32]:
        """Return the first `channels` channels of a chunk multiplied by the planned gain."""
        positions = np.arange(self._position, self._position + len(frames)) + 0.5
        self._position += len(frames)
        if len(self._gain):
            decibels = np.interp(positions, self._centers, self._gain)
        else:
            decibels = np.zeros(len(frames))
        factors = np.power(10.0, decibels / 20)[:, None]
        return np.asarray(frames[:, :channels] * factors, dtype=np.float32)
