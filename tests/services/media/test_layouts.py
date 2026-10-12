import pytest

from phmaster.services.media.layouts import (
    channel_names,
    has_center,
    kept_layout,
    resolve_layout,
)


@pytest.mark.parametrize(
    ("layout", "channels", "expected"),
    [
        ("5.1(side)", 6, "5.1(side)"),
        ("5.1 (side)", 6, "5.1"),
        ("stereo", 2, "stereo"),
        ("", 6, "5.1"),
        (None, 2, "stereo"),
        ("weird", 8, "7.1"),
        (None, 24, None),
        (None, 3, None),
        ("unknown", 4, None),
        (None, 1, "mono"),
    ],
)
def test_resolve_layout(layout: str | None, channels: int, expected: str | None) -> None:
    assert resolve_layout(layout, channels) == expected


def test_channel_names_follow_ffmpeg_order() -> None:
    assert channel_names("5.1") == ("FL", "FR", "FC", "LFE", "BL", "BR")


@pytest.mark.parametrize(
    ("layout", "expected"), [("5.1", True), ("mono", True), ("stereo", False), (None, False)]
)
def test_has_center(layout: str | None, expected: bool) -> None:
    assert has_center(layout) is expected


@pytest.mark.parametrize(
    ("layout", "expected"),
    [("stereo", "stereo"), ("5.1(side)", "5.1(side)"), ("7.1", "5.1"), (None, "5.1")],
)
def test_kept_layout_folds_more_than_six_channels(layout: str | None, expected: str) -> None:
    assert kept_layout(layout) == expected
