from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter1d
from scipy.signal import sosfilt

Signal = NDArray[np.float64]

# Rate of decoded PCM; the K-weighting coefficients below are designed for it.
SAMPLE_RATE = 48_000
BLOCK_SECONDS = 0.01
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_SECONDS)
MOMENTARY_SECONDS = 0.4
SHORT_TERM_SECONDS = 3.0
ABSOLUTE_GATE = -70.0
RELATIVE_GATE = -10.0
LRA_RELATIVE_GATE = -20.0
GATING_HOP_SECONDS = 0.1
# Fraction of gating blocks with active dialogue needed to trust a dialogue-gated reference.
MIN_DIALOG_FRACTION = 0.1
DIALOG_WINDOW = 10.0
DIALOG_PERCENTILE = 80.0
_POWER_FLOOR = 1e-12

# ITU-R BS.1770-4 K-weighting at 48 kHz: high-shelf pre-filter, then RLB high-pass.
K_WEIGHTING = np.array(
    [
        [
            1.53512485958697,
            -2.69169618940638,
            1.19839281085285,
            1.0,
            -1.69065929318241,
            0.73248077421585,
        ],
        [1.0, -2.0, 1.0, 1.0, -1.99004745483398, 0.99007225036621],
    ]
)

_SURROUND = frozenset({"BL", "BR", "SL", "SR", "BC", "TBL", "TBR", "TBC", "TSL", "TSR"})
_SURROUND_WEIGHT = 1.41


def channel_weights(names: Sequence[str]) -> list[float]:
    """Return BS.1770 channel weights: surround 1.41, LFE excluded, others 1.0."""
    return [
        0.0 if name.startswith("LFE") else _SURROUND_WEIGHT if name in _SURROUND else 1.0
        for name in names
    ]


def to_lufs(power: Signal | float) -> Signal:
    """Convert K-weighted mean-square power to LUFS."""
    return np.asarray(-0.691 + 10 * np.log10(np.maximum(power, _POWER_FLOOR)), dtype=np.float64)


@dataclass(frozen=True, slots=True)
class LoudnessEnvelope:
    """K-weighted power per 10 ms block for the program and, if known, the dialogue channel."""

    program: Signal
    dialog: Signal | None
    peak: float

    @property
    def duration(self) -> float:
        """Length of the measured audio in seconds."""
        return len(self.program) * BLOCK_SECONDS


class BlockMeter:
    """Accumulate K-weighted block power from streamed (frames, channels) chunks.

    Channels with zero weight do not count toward the program; `dialog_index` selects the
    channel measured separately as dialogue.
    """

    def __init__(self, weights: Sequence[float], dialog_index: int | None = None) -> None:
        self._weights = np.asarray(weights, dtype=np.float64)
        self._dialog_index = dialog_index
        self._program_channels = np.flatnonzero(self._weights)
        self._state = np.zeros((len(K_WEIGHTING), 2, len(weights)))
        self._remainder = np.empty((0, len(weights)))
        self._program: list[Signal] = []
        self._dialog: list[Signal] = []
        self._peak = 0.0

    def feed(self, frames: NDArray[np.floating]) -> None:
        """Measure one chunk of interleaved samples."""
        if len(frames) == 0:
            return
        samples = np.asarray(frames, dtype=np.float64)
        if len(self._program_channels):
            self._peak = max(self._peak, float(np.max(np.abs(samples[:, self._program_channels]))))
        weighted, self._state = sosfilt(K_WEIGHTING, samples, axis=0, zi=self._state)
        squares = np.concatenate([self._remainder, weighted * weighted])
        usable = len(squares) - len(squares) % BLOCK_SIZE
        self._remainder = squares[usable:]
        if usable:
            self._append(squares[:usable].reshape(-1, BLOCK_SIZE, squares.shape[1]).mean(axis=1))

    def _append(self, mean_squares: Signal) -> None:
        self._program.append(mean_squares @ self._weights)
        if self._dialog_index is not None:
            self._dialog.append(mean_squares[:, self._dialog_index])

    def finish(self) -> LoudnessEnvelope:
        """Flush the last partial block and return the envelope."""
        if len(self._remainder):
            self._append(self._remainder.mean(axis=0, keepdims=True))
            self._remainder = self._remainder[:0]
        program = np.concatenate(self._program) if self._program else np.zeros(0)
        dialog = None
        if self._dialog_index is not None:
            dialog = np.concatenate(self._dialog) if self._dialog else np.zeros(0)
        return LoudnessEnvelope(program=program, dialog=dialog, peak=self._peak)


def windowed_power(power: Signal, seconds: float) -> Signal:
    """Return the centered moving average of block power over a window."""
    if len(power) == 0:
        return power
    size = max(1, round(seconds / BLOCK_SECONDS))
    return np.asarray(uniform_filter1d(power, size, mode="nearest"), dtype=np.float64)


def _gating_blocks(power: Signal, seconds: float) -> Signal:
    size = round(seconds / BLOCK_SECONDS)
    hop = round(GATING_HOP_SECONDS / BLOCK_SECONDS)
    if len(power) <= size:
        return np.asarray([power.mean()]) if len(power) else power
    cumulative = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, len(power) - size + 1, hop)
    return np.asarray((cumulative[starts + size] - cumulative[starts]) / size, dtype=np.float64)


def _gated_mean(blocks: Signal, relative_gate: float) -> tuple[float | None, NDArray[np.bool_]]:
    loud = to_lufs(blocks)
    passed = loud > ABSOLUTE_GATE
    if not passed.any():
        return None, passed
    threshold = float(to_lufs(blocks[passed].mean())) + relative_gate
    passed &= loud > threshold
    return float(blocks[passed].mean()), passed


def integrated_loudness(power: Signal) -> float | None:
    """Return BS.1770 gated integrated loudness in LUFS, or None for silence."""
    mean, _ = _gated_mean(_gating_blocks(power, MOMENTARY_SECONDS), RELATIVE_GATE)
    return None if mean is None else float(to_lufs(mean))


def loudness_range(power: Signal) -> float:
    """Return the EBU Tech 3342 loudness range (LRA) in LU."""
    blocks = _gating_blocks(power, SHORT_TERM_SECONDS)
    _, passed = _gated_mean(blocks, LRA_RELATIVE_GATE)
    if passed.sum() < 2:  # noqa: PLR2004 - a range needs two values
        return 0.0
    low, high = np.percentile(to_lufs(blocks[passed]), [10, 95])
    return float(high - low)


def typical_level(blocks: Signal, percentile: float = 50.0) -> float | None:
    """Return a percentile (the median by default) of non-silent block loudness in LUFS.

    Blocks below the absolute gate, and blocks 20 LU below their median, are ignored, so
    near-silence does not pull the level down and loud scenes cannot gate out quiet ones.
    None means silence.
    """
    loudness = to_lufs(blocks)
    gated = loudness[loudness > ABSOLUTE_GATE]
    if not len(gated):
        return None
    gated = gated[gated > np.median(gated) + LRA_RELATIVE_GATE]
    return float(np.percentile(gated, percentile))


def reference_loudness(envelope: LoudnessEnvelope) -> float | None:
    """Return the typical program loudness while dialogue is active, in LUFS.

    Dialogue is active where the dialogue channel is within 10 LU of its speech level, the
    80th percentile of its loudness, since speech is louder than the pauses between lines;
    without enough such blocks the typical level of the whole program is used. None means
    silence.
    """
    program = _gating_blocks(envelope.program, MOMENTARY_SECONDS)
    overall = typical_level(program)
    if overall is None:
        return None
    if envelope.dialog is not None:
        dialog = _gating_blocks(envelope.dialog, MOMENTARY_SECONDS)
        dialog_level = typical_level(dialog, DIALOG_PERCENTILE)
        if dialog_level is not None:
            program_lufs = to_lufs(program)
            gated = program_lufs > overall + LRA_RELATIVE_GATE
            active = gated & (to_lufs(dialog) > dialog_level - DIALOG_WINDOW)
            if active.sum() >= MIN_DIALOG_FRACTION * gated.sum():
                return float(np.median(program_lufs[active]))
    return overall
