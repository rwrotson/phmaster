from pathlib import Path

import cli_app.utils.misc as _misc_module
from cli_app.utils.misc import find_project_root


def test_find_project_root_contains_pyproject_toml() -> None:
    root = find_project_root()
    assert (root / "pyproject.toml").exists()


def test_find_project_root_unknown_marker_falls_back_to_module_parent() -> None:
    expected = Path(_misc_module.__file__).parent.resolve()
    result = find_project_root(marker="_nonexistent_marker_xyz_")
    assert result == expected
