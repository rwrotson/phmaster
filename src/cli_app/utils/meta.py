import json
import re
from dataclasses import dataclass
from email.utils import parseaddr
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Self, TypedDict, cast


class DependencyDict(TypedDict):
    """Identify an installed dependency and its version."""

    name: str
    version: str


class ContactDict(TypedDict):
    """Store a package contact's name and email address."""

    name: str
    email: str


class MetaDict(TypedDict, total=False):
    """Describe the available installed distribution metadata."""

    metadata_version: str
    name: str
    version: str
    summary: str
    description: str
    authors: list[ContactDict]
    maintainers: list[ContactDict]
    classifiers: list[str]
    keywords: list[str]
    requires_python: str
    readme: str
    license_file: str
    url: str
    dependencies: list[DependencyDict]


@dataclass(slots=True, frozen=True)
class Meta:
    """Load and expose metadata for the installed application."""

    data: MetaDict

    @staticmethod
    def _find_dist_name_from_direct_url(pkg_file: Path) -> str | None:
        for dist in metadata.distributions():
            raw = dist.read_text("direct_url.json")
            if raw:
                try:
                    url = json.loads(raw).get("url", "")
                    dist_dir = Path(url.removeprefix("file://"))
                    if pkg_file.is_relative_to(dist_dir):
                        return dist.name
                except ValueError, TypeError:
                    continue
        return None

    @classmethod
    def load_from_installed_package(cls) -> Self:
        """Load metadata for the distribution containing this package."""
        pkg_file = Path(__file__).resolve()

        # Editable uv_build installs omit top_level.txt, so resolve direct_url.json first.
        dist_name = cls._find_dist_name_from_direct_url(pkg_file)

        if dist_name is None:
            top_level_pkg = __package__.split(".")[0] if __package__ else None
            if top_level_pkg:
                dist_names = metadata.packages_distributions().get(top_level_pkg)
                if dist_names:
                    dist_name = dist_names[0]

        if dist_name is None:
            return cls(data=cls._get_fallback_meta("Unknown"))

        try:
            meta_json = metadata.metadata(dist_name).json

            author_email = cast(str, meta_json.pop("author_email", ""))
            requires_dist = meta_json.pop("requires_dist", [])

            meta_dict_keys = MetaDict.__annotations__.keys()
            meta = cast(MetaDict, {k: v for k, v in meta_json.items() if k in meta_dict_keys})

            authors: list[ContactDict] = []
            for author_string in author_email.split(","):
                name, email = parseaddr(author_string)
                authors.append({"name": name, "email": email})
            meta["authors"] = authors
            meta["dependencies"] = cls._get_installed_dependencies(cast(list[str], requires_dist))

            return cls(data=meta)

        except metadata.PackageNotFoundError:
            return cls(data=cls._get_fallback_meta(dist_name))

    @staticmethod
    def _get_installed_dependencies(requires_dist: list[str]) -> list[DependencyDict]:
        pkg_name_pattern = re.compile(r"^[a-zA-Z0-9._-]+")
        pkg_names = [
            m.group(0).lower()
            for s in requires_dist
            if (m := pkg_name_pattern.match(s)) is not None
        ]

        installed: dict[str, str] = {}
        for dist in metadata.distributions():
            if dist.name.lower() in pkg_names:
                installed[dist.name] = dist.version

        return [{"name": name, "version": version} for name, version in sorted(installed.items())]

    @staticmethod
    def _get_fallback_meta(pkg_name: str) -> MetaDict:
        return {
            "name": f"{pkg_name} (not installed)",
            "version": "0.0.0-dev",
            "description": "Project metadata unavailable.",
            "dependencies": [],
        }

    def __getitem__(self, item: str) -> str | list[ContactDict] | list[DependencyDict] | None:
        return cast(str | list[ContactDict] | list[DependencyDict] | None, self.data.get(item))

    def __str__(self) -> str:
        return str(self.data)


@cache
def get_project_meta() -> Meta:
    """Return cached metadata for the installed application."""
    return Meta.load_from_installed_package()
