import sys
from pathlib import Path

import numpy as np
import pytest

from phmaster.services.errors import FfmpegError
from phmaster.services.media.pcm import PcmWriter, read_pcm

_EMIT = "import sys; sys.stdout.buffer.write(bytes(range(32)) * 3); sys.stdout.flush()"


def test_read_pcm_yields_whole_frames() -> None:
    with read_pcm([sys.executable, "-c", _EMIT], channels=2, chunk_frames=3) as chunks:
        shapes = [chunk.shape for chunk in chunks]
    assert sum(shape[0] for shape in shapes) == 12
    assert all(shape[1] == 2 for shape in shapes)


def test_read_pcm_keeps_partial_frames_across_reads() -> None:
    with read_pcm([sys.executable, "-c", _EMIT], channels=3, chunk_frames=1) as chunks:
        total = sum(len(chunk) for chunk in chunks)
    assert total == 8


def test_read_pcm_raises_on_failure() -> None:
    script = "import sys; sys.stderr.write('bad input'); sys.exit(2)"
    with (
        pytest.raises(FfmpegError, match="bad input"),
        read_pcm([sys.executable, "-c", script], channels=1, chunk_frames=8) as chunks,
    ):
        list(chunks)


def test_read_pcm_terminates_process_on_early_exit() -> None:
    script = "import sys\nwhile True: sys.stdout.buffer.write(b'\\0' * 4096)"
    with read_pcm([sys.executable, "-c", script], channels=1, chunk_frames=16) as chunks:
        first = next(iter(chunks))
    assert first.shape == (16, 1)


def test_pcm_writer_sends_samples(tmp_path: Path) -> None:
    out = tmp_path / "out.raw"
    script = f"import sys; open({str(out)!r}, 'wb').write(sys.stdin.buffer.read())"
    with PcmWriter([sys.executable, "-c", script]) as writer:
        writer.write(np.ones((4, 2), dtype=np.float64))
    assert np.frombuffer(out.read_bytes(), dtype="<f4").tolist() == [1.0] * 8


def test_pcm_writer_reports_encoder_failure() -> None:
    script = "import sys; sys.stdin.read(); sys.stderr.write('encoder broke'); sys.exit(1)"
    writer = PcmWriter([sys.executable, "-c", script])
    writer.write(np.zeros((1, 1), dtype=np.float32))
    with pytest.raises(FfmpegError, match="encoder broke"):
        writer.close()


def test_pcm_writer_reports_early_encoder_exit() -> None:
    script = "import sys; sys.stderr.write('died'); sys.exit(4)"
    writer = PcmWriter([sys.executable, "-c", script])
    chunk = np.zeros((65536, 1), dtype=np.float32)

    def feed() -> None:
        for _ in range(1000):
            writer.write(chunk)

    with pytest.raises(FfmpegError, match="died"):
        feed()
    writer.abort()


def test_pcm_writer_aborts_on_exception() -> None:
    script = "import sys, time; time.sleep(10)"
    with pytest.raises(RuntimeError), PcmWriter([sys.executable, "-c", script]):
        raise RuntimeError
