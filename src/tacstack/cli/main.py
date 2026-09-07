"""TacStack CLI: contract demos plus Open-X-Tactile dataset tooling."""

import json
from pathlib import Path
from typing import NoReturn

import typer

from tacstack import __version__
from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter, OpenXTactileArchive
from tacstack.core import TactileEvent
from tacstack.core.serialization import to_debug_json
from tacstack.integrations.mcap import observation_record, write_episode_mcap

app = typer.Typer(no_args_is_help=True, help="TacStack tactile contracts (development scaffold).")
dataset_app = typer.Typer(
    no_args_is_help=True, help="Inspect and convert Open-X-Tactile (FTP-1) archives."
)
app.add_typer(dataset_app, name="dataset")


@app.command()
def version() -> None:
    """Print the development version."""
    typer.echo(__version__)


@app.command()
def contract_demo() -> None:
    """Print a synthetic event to verify installation. No sensor or inference is used."""
    event = TactileEvent(
        timestamp_ns=0,
        sensor_id="synthetic",
        kind="contact_begin",
        probability=1.0,
        model_id="contract-example",
        latency_ms=0.0,
        metadata={"synthetic": True},
    )
    typer.echo(to_debug_json(event))


def _fail(error: Exception) -> NoReturn:
    typer.echo(f"error: {error}", err=True)
    raise typer.Exit(code=1)


def _resolve_task(archive: OpenXTactileArchive, task: str) -> str:
    names = archive.task_names()
    if task:
        if task not in names:
            raise KeyError(f"task {task!r} not found; available: {', '.join(names) or 'none'}")
        return task
    if len(names) == 1:
        return names[0]
    raise ValueError(f"archive has multiple tasks; --task is required: {', '.join(names)}")


def _open_episode_adapter(
    source: Path,
    task: str,
    episode: int,
    stream: str | None,
    rate_hz: float | None,
) -> OpenXTactileAdapter:
    try:
        with OpenXTactileArchive(source) as archive:
            resolved = _resolve_task(archive, task)
        adapter = OpenXTactileAdapter(
            source, task=resolved, episode=episode, stream=stream, rate_hz=rate_hz
        )
        adapter.open()
    except (IndexError, KeyError, OSError, RuntimeError, ValueError) as error:
        _fail(error)
    return adapter


@dataset_app.command("list")
def dataset_list(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
) -> None:
    """List tasks, episode counts and tactile streams in an OXT archive."""
    try:
        with OpenXTactileArchive(source) as archive:
            for name in archive.task_names():
                info = archive.open_task(name).info()
                streams = ", ".join(
                    f"{s.stream}({s.sensor},{s.kind},x{s.areas})" for s in info.streams
                )
                typer.echo(
                    f"{info.name}: episodes={info.episodes} frames={info.frames} "
                    f"streams=[{streams}]"
                )
    except (KeyError, OSError, ValueError) as error:
        _fail(error)


@dataset_app.command("inspect")
def dataset_inspect(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
    task: str = typer.Option("", help="Task name; optional when the archive holds exactly one."),
    episode: int = typer.Option(0, min=0, help="Episode index."),
    stream: str | None = typer.Option(
        None, help="Tactile stream name; optional when the task has one."
    ),
    rate_hz: float | None = typer.Option(
        None, help="Assumed frame rate; converts index timestamps to ns."
    ),
) -> None:
    """Print the sensor descriptor and the first observation of one episode."""
    adapter = _open_episode_adapter(source, task, episode, stream, rate_hz)
    try:
        descriptor = adapter.descriptor()
        first = adapter.read()
    finally:
        adapter.close()
    typer.echo(to_debug_json(descriptor))
    typer.echo(json.dumps(observation_record(first), ensure_ascii=False, allow_nan=False))


@dataset_app.command("convert")
def dataset_convert(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
    out: Path = typer.Option(..., help="Output MCAP file path."),
    task: str = typer.Option("", help="Task name; optional when the archive holds exactly one."),
    episode: int = typer.Option(0, min=0, help="Episode index."),
    stream: str | None = typer.Option(
        None, help="Tactile stream name; optional when the task has one."
    ),
    rate_hz: float | None = typer.Option(
        None, help="Assumed frame rate; converts index timestamps to ns."
    ),
) -> None:
    """Convert one episode to an MCAP recording (one JSON message per frame)."""
    adapter = _open_episode_adapter(source, task, episode, stream, rate_hz)
    try:
        summary = write_episode_mcap(observations(adapter), out)
    finally:
        adapter.close()
    typer.echo(
        f"wrote {summary.messages} observations to {summary.path} "
        f"(timestamps {summary.first_timestamp_ns}..{summary.last_timestamp_ns})"
    )


if __name__ == "__main__":
    app()
