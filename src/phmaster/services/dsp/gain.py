from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d, maximum_filter1d, median_filter, minimum_filter1d

from phmaster.services.dsp.loudness import (
    BLOCK_SECONDS,
    BLOCK_SIZE,
    MOMENTARY_SECONDS,
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
# The slow gain follows the median scene level over this window, so it reacts only to level
# changes lasting longer than half of it; shorter loud moments are left to the compressor,
# and shorter fades and pauses keep the gain of the scene around them.
SUSTAIN_SECONDS = 8.0
SUSTAIN_STEP = 10


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
    momentary = _bridge_silence(power, reference)
    if momentary is None:
        return np.full(len(power), static_gain)
    level = _sustained_level(momentary)
    deviation = np.clip(preset.strength * (reference - level), -preset.max_cut, preset.max_boost)
    sigma = preset.smoothing / BLOCK_SECONDS
    return np.asarray(
        gaussian_filter1d(static_gain + deviation, sigma, mode="nearest"), dtype=np.float64
    )


def _sustained_level(loudness: Signal) -> Signal:
    """Return the running median of loudness, computed on a 100 ms grid."""
    index = np.arange(len(loudness))
    coarse = index[::SUSTAIN_STEP]
    size = round(SUSTAIN_SECONDS / (BLOCK_SECONDS * SUSTAIN_STEP)) | 1
    median = median_filter(loudness[coarse], size=size, mode="nearest")
    return np.asarray(np.interp(index, coarse, median), dtype=np.float64)


def _bridge_silence(power: Signal, reference: float) -> Signal | None:
    """Return momentary loudness with silent stretches interpolated from their neighbours.

    None means the whole track is silent.
    """
    momentary = to_lufs(windowed_power(power, MOMENTARY_SECONDS))
    silent = momentary < max(SILENCE_FLOOR, reference + SILENCE_RELATIVE)
    # A block only reads as silent once its window is almost entirely silent, so widen by a
    # whole window on each side to also bridge blocks whose window touches the silence.
    margin = 2 * round(MOMENTARY_SECONDS / BLOCK_SECONDS) + 1
    silent = maximum_filter1d(silent, margin, mode="nearest")
    if silent.all():
        return None
    if silent.any():
        index = np.arange(len(power))
        momentary[silent] = np.interp(index[silent], index[~silent], momentary[~silent])
    return momentary


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
    """Reach every dip `lookahead` seconds early and ease into it, without overshooting.

    A forward minimum holds each dip over the preceding lookahead window; a one-pole filter run
    backwards in time then lowers the gain gradually before it. Both steps only lower the
    curve, so the gain at a dip never exceeds what the dip needs.
    """
    if len(gain) == 0:
        return gain
    half = max(1, round(lookahead / 2 / BLOCK_SECONDS))
    held = minimum_filter1d(gain, 2 * half + 1, mode="nearest", origin=-half)
    coefficient = float(np.exp(-3 * BLOCK_SECONDS / lookahead))
    out = held.copy()
    for index in range(len(out) - 2, -1, -1):
        following = out[index + 1]
        if out[index] > following:
            out[index] = following + (1 - coefficient) * (out[index] - following)
    return out


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
