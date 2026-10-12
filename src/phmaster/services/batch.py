from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from phmaster.services.errors import InvalidInputError, ServiceError
from phmaster.services.media.tools import Tools
from phmaster.services.normalize import NormalizeRequest, NormalizeResult, normalize_file
from phmaster.services.pipeline import ProgressSink

VIDEO_EXTENSIONS = frozenset(
    {
        ".avi",
        ".flv",
        ".m2ts",
        ".m4v",
        ".mk3d",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".mts",
        ".ogv",
        ".ts",
        ".vob",
        ".webm",
        ".wmv",
    }
)


@dataclass(frozen=True, slots=True)
class FileFailure:
    """A file that could not be processed."""

    path: Path
    error: ServiceError


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Outcome of processing several files."""

    results: tuple[NormalizeResult, ...]
    failures: tuple[FileFailure, ...]

    @property
    def exit_code(self) -> int:
        """Exit code of the first failure, or 0 when every file succeeded."""
        return self.failures[0].error.exit_code if self.failures else 0


def discover(paths: Iterable[Path], *, recursive: bool, suffix: str) -> list[Path]:
    """Expand files and directories into video files, skipping hidden files and earlier outputs."""
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            candidates = path.rglob("*") if recursive else path.iterdir()
            found.extend(
                sorted(
                    candidate
                    for candidate in candidates
                    if candidate.is_file()
                    and candidate.suffix.lower() in VIDEO_EXTENSIONS
                    and not candidate.stem.endswith(suffix)
                    and not _is_hidden(candidate.relative_to(path))
                )
            )
        else:
            raise InvalidInputError(f"path not found: {path}")
    return list(dict.fromkeys(found))


def _is_hidden(relative: Path) -> bool:
    # Hidden directories include `.phmaster-*` work directories left by an interrupted run.
    return any(part.startswith(".") for part in relative.parts)


def process_files(
    tools: Tools,
    files: Iterable[Path],
    template: NormalizeRequest,
    progress: ProgressSink | None = None,
    on_result: Callable[[NormalizeResult | FileFailure], None] | None = None,
) -> BatchResult:
    """Normalize each file with the template request, collecting failures instead of stopping."""
    results: list[NormalizeResult] = []
    failures: list[FileFailure] = []
    for path in files:
        outcome: NormalizeResult | FileFailure
        try:
            outcome = normalize_file(tools, replace(template, source=path), progress)
        except ServiceError as error:
            outcome = FileFailure(path, error)
            failures.append(outcome)
        else:
            results.append(outcome)
        if on_result is not None:
            on_result(outcome)
    return BatchResult(tuple(results), tuple(failures))
