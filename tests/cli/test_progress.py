from io import StringIO

from rich.console import Console
from rich.progress import Progress

from phmaster.cli.context import AppContext
from phmaster.cli.progress import RichProgressSink, progress_sink
from phmaster.config import load_settings
from phmaster.utils.output import OutputFormat


def test_sink_reuses_one_task() -> None:
    progress = Progress(console=Console(file=StringIO()), auto_refresh=False)
    sink = RichProgressSink(progress)

    sink.advance(1.0)
    sink.stage("first", 10.0)
    sink.advance(4.0)
    sink.stage("second", None)

    (task,) = progress.tasks
    assert task.description == "second"
    assert task.total is None
    assert task.completed == 0


def test_progress_is_hidden_for_json() -> None:
    context = AppContext(
        settings=load_settings(), console=Console(file=StringIO()), output_format=OutputFormat.json
    )
    with progress_sink(context) as sink:
        sink.stage("step", 1.0)
        sink.advance(1.0)
