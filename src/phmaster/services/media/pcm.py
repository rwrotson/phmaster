import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from types import TracebackType
from typing import IO, Self

import numpy as np
from numpy.typing import NDArray

from phmaster.services.errors import FfmpegError

Frames = NDArray[np.float32]
_BYTES_PER_SAMPLE = 4


@contextmanager
def read_pcm(command: list[str], channels: int, chunk_frames: int) -> Iterator[Iterator[Frames]]:
    """Run a decoding command and yield its f32le stdout as (frames, channels) chunks.

    The process is checked when the iterator is exhausted; leaving early terminates it.
    """
    with tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr)  # noqa: S603
        try:
            yield _iter_chunks(process, stderr, channels, chunk_frames, Path(command[0]).name)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()


def _iter_chunks(
    process: subprocess.Popen[bytes],
    stderr: IO[bytes],
    channels: int,
    chunk_frames: int,
    program: str,
) -> Iterator[Frames]:
    stdout = process.stdout
    if stdout is None:  # pragma: no cover - Popen was created with stdout=PIPE
        raise RuntimeError("decoder stdout is not a pipe")
    frame_bytes = channels * _BYTES_PER_SAMPLE
    pending = b""
    while chunk := stdout.read(chunk_frames * frame_bytes):
        data = pending + chunk
        usable = len(data) - len(data) % frame_bytes
        pending = data[usable:]
        if usable:
            yield np.frombuffer(data[:usable], dtype="<f4").reshape(-1, channels)
    _check(process, stderr, program)


class PcmWriter:
    """Feed f32le chunks to an encoding command's stdin."""

    def __init__(self, command: list[str]) -> None:
        self._stderr = tempfile.TemporaryFile()  # noqa: SIM115 - closed in close()
        self._process = subprocess.Popen(  # noqa: S603
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._stderr
        )
        self._program = Path(command[0]).name

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()

    def write(self, frames: Frames) -> None:
        """Send one chunk of interleaved samples to the encoder."""
        stdin = self._process.stdin
        if stdin is None:  # pragma: no cover - Popen was created with stdin=PIPE
            raise RuntimeError("encoder stdin is not a pipe")
        try:
            stdin.write(np.ascontiguousarray(frames, dtype="<f4").tobytes())
        except BrokenPipeError:
            self._process.wait()
            _check(self._process, self._stderr, self._program)
            raise

    def close(self) -> None:
        """Finish the stream and raise FfmpegError if the encoder failed."""
        try:
            if self._process.stdin is not None:
                with suppress(BrokenPipeError):
                    self._process.stdin.close()
            _check(self._process, self._stderr, self._program)
        finally:
            self._stderr.close()

    def abort(self) -> None:
        """Stop the encoder without checking its result."""
        if self._process.poll() is None:
            self._process.kill()
        self._process.wait()
        if self._process.stdin is not None:
            with suppress(BrokenPipeError):
                self._process.stdin.close()
        self._stderr.close()


def _check(process: subprocess.Popen[bytes], stderr: IO[bytes], program: str) -> None:
    returncode = process.wait()
    if returncode != 0:
        stderr.seek(0)
        raise FfmpegError(program, returncode, stderr.read().decode(errors="replace"))
