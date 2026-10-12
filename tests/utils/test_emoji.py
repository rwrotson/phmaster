from cli_app.utils.emoji import Emoji


def test_emoji_values() -> None:
    assert str(Emoji.ROCKET) == "🚀"
    assert str(Emoji.STOP_SIGN) == "🛑"
    assert str(Emoji.SUNGLASSES) == "😎"
    assert str(Emoji.PRAY) == "🙏"
    assert {e.name for e in Emoji} == {"ROCKET", "STOP_SIGN", "SUNGLASSES", "PRAY"}
