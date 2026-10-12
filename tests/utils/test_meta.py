import json
import re
from importlib import metadata
from pathlib import Path

import pytest

from cli_app.utils.meta import Meta, MetaDict, get_project_meta


def test_fallback_meta() -> None:
    meta = Meta._get_fallback_meta("MyPkg")
    assert meta["name"] == "MyPkg (not installed)"
    assert meta["version"] == "0.0.0-dev"
    assert meta["dependencies"] == []


def test_load_from_installed_package_name_and_version() -> None:
    m = Meta.load_from_installed_package()
    assert m["name"] == "cli-app"
    assert re.match(r"\d+\.\d+\.\d+", str(m["version"]))


def test_meta_getitem_present_key() -> None:
    data: MetaDict = {"name": "test-app", "version": "1.2.3"}
    m = Meta(data=data)
    assert m["name"] == "test-app"
    assert m["version"] == "1.2.3"


def test_meta_getitem_missing_key_returns_none() -> None:
    data: MetaDict = {"name": "test-app"}
    m = Meta(data=data)
    assert m["nonexistent_key"] is None


def test_meta_str_contains_data() -> None:
    data: MetaDict = {"name": "test-app"}
    m = Meta(data=data)
    assert "test-app" in str(m)


def test_get_installed_dependencies_empty_input() -> None:
    deps = Meta._get_installed_dependencies([])
    assert deps == []


def test_get_installed_dependencies_known_package() -> None:
    deps = Meta._get_installed_dependencies(["typer>=0.16.0"])
    assert "typer" in {d["name"].lower() for d in deps}


def test_get_installed_dependencies_returns_sorted() -> None:
    deps = Meta._get_installed_dependencies(["typer>=0.16.0", "pydantic-settings>=2.0"])
    names = [d["name"] for d in deps]
    assert names == sorted(names)


def test_get_project_meta_is_cached() -> None:
    assert get_project_meta() is get_project_meta()


class _FakeDist:
    def __init__(self, name: str, direct_url: str | None) -> None:
        self.name = name
        self._direct_url = direct_url

    def read_text(self, _filename: str) -> str | None:
        return self._direct_url


def test_find_dist_name_skips_invalid_direct_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dists = [
        _FakeDist("broken", "not json"),
        _FakeDist("other", json.dumps({"url": "file:///elsewhere"})),
        _FakeDist("mine", json.dumps({"url": f"file://{tmp_path}"})),
    ]
    monkeypatch.setattr(metadata, "distributions", lambda: dists)

    assert Meta._find_dist_name_from_direct_url(tmp_path / "pkg.py") == "mine"


def test_load_falls_back_to_packages_distributions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Meta, "_find_dist_name_from_direct_url", staticmethod(lambda _: None))
    monkeypatch.setattr(metadata, "packages_distributions", lambda: {"cli_app": ["cli-app"]})

    assert Meta.load_from_installed_package()["name"] == "cli-app"


def test_load_returns_unknown_without_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Meta, "_find_dist_name_from_direct_url", staticmethod(lambda _: None))
    monkeypatch.setattr(metadata, "packages_distributions", dict)

    assert Meta.load_from_installed_package()["name"] == "Unknown (not installed)"


def test_load_returns_fallback_for_missing_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Meta, "_find_dist_name_from_direct_url", staticmethod(lambda _: "ghost"))

    def missing(name: str) -> None:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "metadata", missing)

    assert Meta.load_from_installed_package()["name"] == "ghost (not installed)"
