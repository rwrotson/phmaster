import pytest

from phmaster.services.media.tools import Tools, find_tools


@pytest.fixture
def tools() -> Tools:
    return find_tools()
