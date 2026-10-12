from cli_app.utils.format import get_theme


def test_get_theme_has_expected_styles() -> None:
    styles = get_theme().styles
    assert "info" in styles
    assert "warning" in styles
    assert "danger" in styles


def test_get_theme_is_cached() -> None:
    assert get_theme() is get_theme()
