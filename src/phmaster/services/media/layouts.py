# Channel order of ffmpeg's standard layouts (`ffmpeg -layouts`).
CHANNEL_LAYOUTS: dict[str, tuple[str, ...]] = {
    "mono": ("FC",),
    "stereo": ("FL", "FR"),
    "2.1": ("FL", "FR", "LFE"),
    "3.0": ("FL", "FR", "FC"),
    "3.0(back)": ("FL", "FR", "BC"),
    "4.0": ("FL", "FR", "FC", "BC"),
    "quad": ("FL", "FR", "BL", "BR"),
    "quad(side)": ("FL", "FR", "SL", "SR"),
    "3.1": ("FL", "FR", "FC", "LFE"),
    "5.0": ("FL", "FR", "FC", "BL", "BR"),
    "5.0(side)": ("FL", "FR", "FC", "SL", "SR"),
    "4.1": ("FL", "FR", "FC", "LFE", "BC"),
    "5.1": ("FL", "FR", "FC", "LFE", "BL", "BR"),
    "5.1(side)": ("FL", "FR", "FC", "LFE", "SL", "SR"),
    "6.0": ("FL", "FR", "FC", "BC", "SL", "SR"),
    "6.0(front)": ("FL", "FR", "FLC", "FRC", "SL", "SR"),
    "hexagonal": ("FL", "FR", "FC", "BL", "BR", "BC"),
    "6.1": ("FL", "FR", "FC", "LFE", "BC", "SL", "SR"),
    "6.1(back)": ("FL", "FR", "FC", "LFE", "BL", "BR", "BC"),
    "6.1(front)": ("FL", "FR", "LFE", "FLC", "FRC", "SL", "SR"),
    "7.0": ("FL", "FR", "FC", "BL", "BR", "SL", "SR"),
    "7.0(front)": ("FL", "FR", "FC", "FLC", "FRC", "SL", "SR"),
    "7.1": ("FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"),
    "7.1(wide)": ("FL", "FR", "FC", "LFE", "BL", "BR", "FLC", "FRC"),
    "7.1(wide-side)": ("FL", "FR", "FC", "LFE", "FLC", "FRC", "SL", "SR"),
    "octagonal": ("FL", "FR", "FC", "BL", "BR", "BC", "SL", "SR"),
}

# Layout ffmpeg assumes for a channel count when a stream has no layout.
DEFAULT_LAYOUTS: dict[int, str] = {
    1: "mono",
    2: "stereo",
    3: "2.1",
    4: "4.0",
    5: "5.0",
    6: "5.1",
    7: "6.1",
    8: "7.1",
}

MAX_KEPT_CHANNELS = 6


def resolve_layout(layout: str | None, channels: int) -> str | None:
    """Return a known layout name for a stream, guessing from the channel count if needed."""
    if layout:
        name = layout.removesuffix(" (side)")
        if name in CHANNEL_LAYOUTS:
            return name
    return DEFAULT_LAYOUTS.get(channels)


def channel_names(layout: str) -> tuple[str, ...]:
    """Return the channel order of a known layout."""
    return CHANNEL_LAYOUTS[layout]


def has_center(layout: str | None) -> bool:
    """Tell whether a layout contains a front center (dialogue) channel."""
    return layout is not None and "FC" in CHANNEL_LAYOUTS.get(layout, ())


def kept_layout(layout: str | None) -> str:
    """Return the output layout that preserves a source layout, folding more than 5.1 into 5.1."""
    if layout is None or layout not in CHANNEL_LAYOUTS:
        return "5.1"
    if len(CHANNEL_LAYOUTS[layout]) > MAX_KEPT_CHANNELS:
        return "5.1"
    return layout
