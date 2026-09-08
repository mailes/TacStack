"""TacStack CLI: contract demos plus Open-X-Tactile dataset tooling."""

import json
from pathlib import Path
from typing import Any, NoReturn

import typer

from tacstack import __version__
from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter, OpenXTactileArchive
from tacstack.annotations import SCHEMA_VERSION, AnnotationLog, TactileMark, normalize_mark, now_ns
from tacstack.core import TactileEvent
from tacstack.core.serialization import to_debug_json
from tacstack.integrations.mcap import observation_record, write_episode_mcap

app = typer.Typer(no_args_is_help=True, help="TacStack tactile contracts (development scaffold).")
dataset_app = typer.Typer(
    no_args_is_help=True, help="Inspect and convert Open-X-Tactile (FTP-1) archives."
)
app.add_typer(dataset_app, name="dataset")
annotate_app = typer.Typer(no_args_is_help=True, help="C/S/U marks stored as Parquet.")
app.add_typer(annotate_app, name="annotate")


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
    extra_arrays: tuple[str, ...] = (),
) -> OpenXTactileAdapter:
    try:
        with OpenXTactileArchive(source) as archive:
            resolved = _resolve_task(archive, task)
        adapter = OpenXTactileAdapter(
            source,
            task=resolved,
            episode=episode,
            stream=stream,
            rate_hz=rate_hz,
            extra_arrays=extra_arrays,
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


@app.command()
def replay(
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
    extra_array: list[str] = typer.Option(
        [],
        "--extra-array",
        help="Embed a named data array per frame (e.g. a camera stream); repeatable.",
    ),
    out: Path | None = typer.Option(None, help="Write a .rrd recording to this path."),
    viewer: bool = typer.Option(False, "--viewer", help="Spawn a local Rerun viewer."),
    connect: str | None = typer.Option(
        None, "--connect", help="Stream to a running viewer (grpc url)."
    ),
    annotations: Path | None = typer.Option(
        None, "--annotations", help="Annotations Parquet file; matching marks are logged."
    ),
) -> None:
    """Replay one tactile episode to Rerun on synchronized timelines.

    Tactile images, taxel heatmaps / F-T series and robot state land on the
    same timeline; scrub and inspect them in the Rerun viewer.
    """
    if out is None and not viewer and connect is None:
        _fail(ValueError("choose at least one sink: --out PATH, --viewer or --connect URL"))
    try:
        from tacstack.integrations.rerun import RerunReplay
    except ImportError as error:  # pragma: no cover - depends on optional extra
        _fail(RuntimeError(f"the rerun SDK is not installed; run: uv sync --extra rerun ({error})"))
    adapter = _open_episode_adapter(
        source, task, episode, stream, rate_hz, extra_arrays=tuple(extra_array)
    )
    replay_logger = RerunReplay()
    if out is not None:
        replay_logger.save(out)
    if connect is not None:
        replay_logger.connect(connect)
    if viewer:
        replay_logger.spawn()
    frames = 0
    resolved_task = resolved_stream = ""
    try:
        # descriptor.sensor_id is "oxt:<task>:<stream>" (built by the adapter)
        sensor_parts = adapter.descriptor().sensor_id.split(":")
        if len(sensor_parts) == 3:
            resolved_task, resolved_stream = sensor_parts[1], sensor_parts[2]
        for observation in observations(adapter):
            replay_logger.log_observation(observation)
            frames += 1
    finally:
        adapter.close()
        replay_logger.flush()
    annotated = 0
    if annotations is not None:
        annotated = _log_matching_annotations(
            replay_logger, annotations, resolved_task, episode, resolved_stream
        )
    message = f"logged {frames} observations to rerun"
    if annotations is not None:
        message += f" and {annotated} annotations"
    typer.echo(message)


def _log_matching_annotations(
    replay_logger: Any,
    annotations: Path,
    resolved_task: str,
    episode: int,
    resolved_stream: str,
) -> int:
    try:
        mark_log = AnnotationLog(annotations)
    except (OSError, RuntimeError, ValueError) as error:
        _fail(error)
    matched = 0
    for mark in mark_log.marks():
        if (
            mark.task == resolved_task
            and mark.episode == episode
            and mark.stream == resolved_stream
        ):
            replay_logger.log_annotation(mark)
            matched += 1
    return matched


@annotate_app.command("add")
def annotate_add(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
    frame: int = typer.Option(..., min=0, help="Episode-relative frame number to mark."),
    mark: str = typer.Option(
        ..., help="C=contact, S=slip, U=unstable grasp (full words also accepted)."
    ),
    user: str = typer.Option(..., help="Annotator name stored with the mark."),
    task: str = typer.Option("", help="Task name; optional when the archive holds exactly one."),
    episode: int = typer.Option(0, min=0, help="Episode index."),
    stream: str | None = typer.Option(
        None, help="Tactile stream name; optional when the task has one."
    ),
    out: Path = typer.Option(
        Path("annotations.parquet"), help="Parquet file to create or append to."
    ),
) -> None:
    """Mark one frame of one episode and append it to the Parquet log."""
    try:
        code = normalize_mark(mark)
    except ValueError as error:
        _fail(error)
    adapter = _open_episode_adapter(source, task, episode, stream, None)
    timestamp_ns: int | None = None
    oxt_index = 0
    stream_name = ""
    task_name = ""
    try:
        sensor_parts = adapter.descriptor().sensor_id.split(":")
        if len(sensor_parts) == 3:
            task_name = sensor_parts[1]
        stream_name = adapter.descriptor().frame_id
        for position, observation in enumerate(observations(adapter)):
            if position == frame:
                timestamp_ns = observation.timestamp_ns
                oxt_index = int(observation.metadata.get("oxt_frame_index", position))
                break
    finally:
        adapter.close()
    if timestamp_ns is None:
        _fail(ValueError(f"frame {frame} is out of range for this episode"))
    entry = TactileMark(
        source=str(source),
        task=task_name,
        episode=episode,
        stream=stream_name,
        frame_index=frame,
        oxt_frame_index=oxt_index,
        timestamp_ns=timestamp_ns,
        mark=code,
        user=user,
        created_ns=now_ns(),
    )
    log = AnnotationLog(out)
    log.add(entry)
    typer.echo(
        f"marked {stream_name} frame {frame} as {code} ({entry.label}); {len(log)} marks in {out}"
    )


@annotate_app.command("show")
def annotate_show(
    path: Path = typer.Argument(..., exists=True, readable=True, help="Annotations Parquet file."),
) -> None:
    """Print all marks stored in an annotations Parquet file."""
    try:
        log = AnnotationLog(path)
    except (OSError, RuntimeError, ValueError) as error:
        _fail(error)
    for mark in log.marks():
        typer.echo(
            f"{mark.mark} {mark.task} ep{mark.episode} {mark.stream} "
            f"frame={mark.frame_index} (oxt {mark.oxt_frame_index}, "
            f"t={mark.timestamp_ns}ns) by {mark.user}"
        )
    typer.echo(f"{len(log)} marks, schema {SCHEMA_VERSION}")


if __name__ == "__main__":
    app()
