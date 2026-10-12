from dataclasses import dataclass
from enum import StrEnum


class PresetName(StrEnum):
    """Built-in normalization strengths."""

    light = "light"
    medium = "medium"
    night = "night"


@dataclass(frozen=True, slots=True)
class Preset:
    """Parameters of the gain planner; levels in LUFS/LU/dB, times in seconds."""

    name: str
    target: float
    """Output loudness of dialogue."""
    strength: float
    """Share (0-1) of each scene's deviation from the dialogue level that is corrected."""
    max_boost: float
    """Largest slow gain above the static normalization gain."""
    max_cut: float
    """Largest slow gain reduction below the static normalization gain."""
    threshold: float
    """Momentary loudness above the target where compression starts."""
    ratio: float
    """Compression ratio above the threshold."""
    knee: float
    """Width of the soft knee around the threshold."""
    lookahead: float
    """How long before a loud moment the gain starts to fall."""
    release: float
    """Time constant of gain recovery after a loud moment."""
    smoothing: float
    """Standard deviation of the Gaussian that smooths the slow gain."""
    ceiling: float
    """True-peak ceiling of the generated track in dBTP."""


PRESETS: dict[PresetName, Preset] = {
    PresetName.light: Preset(
        name="light",
        target=-23.0,
        strength=0.5,
        max_boost=6.0,
        max_cut=6.0,
        threshold=8.0,
        ratio=2.0,
        knee=4.0,
        lookahead=0.15,
        release=0.6,
        smoothing=1.5,
        ceiling=-1.0,
    ),
    PresetName.medium: Preset(
        name="medium",
        target=-21.0,
        strength=0.75,
        max_boost=9.0,
        max_cut=10.0,
        threshold=5.0,
        ratio=3.0,
        knee=4.0,
        lookahead=0.2,
        release=0.8,
        smoothing=1.5,
        ceiling=-1.5,
    ),
    PresetName.night: Preset(
        name="night",
        target=-20.0,
        strength=0.9,
        max_boost=12.0,
        max_cut=15.0,
        threshold=2.0,
        ratio=6.0,
        knee=3.0,
        lookahead=0.25,
        release=1.0,
        smoothing=1.0,
        ceiling=-2.0,
    ),
}
