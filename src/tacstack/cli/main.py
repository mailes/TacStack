"""TacStack CLI: contract demos plus Open-X-Tactile dataset tooling."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn

import typer

from tacstack import __version__
from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter, OpenXTactileArchive
from tacstack.adapters.open_x_tactile.quality import assess_task
from tacstack.annotations import SCHEMA_VERSION, AnnotationLog, TactileMark, normalize_mark, now_ns
from tacstack.benchmark import benchmark_episodes
from tacstack.core import TactileEvent, TactileObservation
from tacstack.core.serialization import to_debug_dict, to_debug_json
from tacstack.integrations.mcap import observation_record, write_episode_mcap
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

app = typer.Typer(no_args_is_help=True, help="TacStack tactile contracts (development scaffold).")
dataset_app = typer.Typer(
    no_args_is_help=True, help="Inspect and convert Open-X-Tactile (FTP-1) archives."
)
app.add_typer(dataset_app, name="dataset")
annotate_app = typer.Typer(no_args_is_help=True, help="C/S/U marks stored as Parquet.")
app.add_typer(annotate_app, name="annotate")
model_app = typer.Typer(no_args_is_help=True, help="Run built-in models over OXT episodes.")
app.add_typer(model_app, name="model")


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


_BUILTIN_MODELS = ("contact", "slip")


def _model_params(
    name: str,
    on_threshold: float | None,
    off_threshold: float | None,
    micro_threshold: float | None,
    slip_threshold: float | None,
    center: float | None,
    gain: float | None,
) -> dict[str, float]:
    if name not in _BUILTIN_MODELS:
        _fail(ValueError(f"unknown model {name!r}; available: {', '.join(_BUILTIN_MODELS)}"))
    params: dict[str, float] = {}
    if name == "contact":
        if on_threshold is not None:
            params["on_threshold"] = on_threshold
        if off_threshold is not None:
            params["off_threshold"] = off_threshold
    else:
        if micro_threshold is not None:
            params["micro_threshold"] = micro_threshold
        if slip_threshold is not None:
            params["slip_threshold"] = slip_threshold
    if center is not None:
        params["center"] = center
    if gain is not None:
        params["gain"] = gain
    return params


def _default_window(name: str) -> int:
    return 1 if name == "contact" else 2


def _build_model(
    name: str,
    params: dict[str, Any],
    artifact: Path | None,
    model_id: str | None,
) -> Any:
    """Build the builtin model, or the ONNX backend when --artifact is given."""
    if artifact is None:
        if model_id is not None:
            params["model_id"] = model_id
        try:
            return builtin_model(name, **params)
        except (KeyError, TypeError, ValueError) as error:
            _fail(error)
    try:
        from tacstack.runtime.onnx_backend import OnnxContactModel, OnnxSlipModel
    except ImportError as error:  # pragma: no cover - depends on optional extra
        _fail(RuntimeError(f"onnxruntime is not installed; run: uv sync --extra onnx ({error})"))
    resolved_id = model_id or f"{name}-onnx"
    try:
        if name == "contact":
            return OnnxContactModel(
                artifact,
                on_threshold=params.get("on_threshold", 0.6),
                off_threshold=params.get("off_threshold", 0.4),
                model_id=resolved_id,
            )
        return OnnxSlipModel(
            artifact,
            micro_threshold=params.get("micro_threshold", 0.4),
            slip_threshold=params.get("slip_threshold", 0.7),
            model_id=resolved_id,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        _fail(error)


def _count_kinds(events: list[TactileEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
    return counts


@model_app.command("run")
def model_run(
    name: str = typer.Argument(..., help="Built-in model: contact or slip."),
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
    window: int | None = typer.Option(
        None, min=1, help="Window frames; defaults to 1 for contact, 2 for slip."
    ),
    on_threshold: float | None = typer.Option(None, help="Contact: begin threshold."),
    off_threshold: float | None = typer.Option(None, help="Contact: end threshold."),
    micro_threshold: float | None = typer.Option(None, help="Slip: micro_slip threshold."),
    slip_threshold: float | None = typer.Option(None, help="Slip: slip threshold."),
    center: float | None = typer.Option(None, help="Logistic center for the score."),
    gain: float | None = typer.Option(None, help="Logistic gain for the score."),
    out: Path | None = typer.Option(
        None, help="Write all events as a JSON array to this path instead of stdout."
    ),
    artifact: Path | None = typer.Option(
        None, "--artifact", help="ONNX scoring artifact; switches to the onnxruntime backend."
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Override the recorded model_id."),
) -> None:
    """Run a built-in model over one episode and emit TactileEvents."""
    params = _model_params(
        name, on_threshold, off_threshold, micro_threshold, slip_threshold, center, gain
    )
    if artifact is not None:
        # the logistic center/gain are baked into the artifact at export time
        params.pop("center", None)
        params.pop("gain", None)
    model = _build_model(name, params, artifact, model_id)
    window_frames = window if window is not None else _default_window(name)
    runtime = Runtime(model, window_frames=window_frames)
    adapter = _open_episode_adapter(source, task, episode, stream, rate_hz)
    events: list[TactileEvent] = []
    frames = 0
    try:
        for observation in observations(adapter):
            frames += 1
            events.extend(runtime.process(observation))
    finally:
        adapter.close()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_debug_json(events) + "\n", encoding="utf-8")
        typer.echo(f"wrote {len(events)} events from {frames} frames to {out}")
    else:
        for event in events:
            typer.echo(to_debug_json(event))
        typer.echo(
            f"summary: {frames} frames, {len(events)} events {_count_kinds(events)} "
            f"(window={window_frames})"
        )


@dataset_app.command("quality")
def dataset_quality(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
    task: str = typer.Option("", help="Task name; optional when the archive holds exactly one."),
    max_frames: int | None = typer.Option(
        None, min=1, help="Scan only the first N frames per stream (default: all)."
    ),
) -> None:
    """Report task health: episodes, timestamp monotonicity, non-finite payload counts."""
    try:
        with OpenXTactileArchive(source) as archive:
            resolved = _resolve_task(archive, task)
            report = assess_task(archive.open_task(resolved), max_frames=max_frames)
    except (KeyError, OSError, ValueError) as error:
        _fail(error)
    typer.echo(to_debug_json(report))
    streams = ", ".join(f"{s['stream']}:{s['nonfinite']} nonfinite" for s in report["streams"])
    typer.echo(
        f"summary: {report['task']} episodes={report['episodes']} frames={report['frames']} "
        f"timestamps_monotonic={report['timestamps']['monotonic']} [{streams}]"
    )


@app.command("benchmark")
def benchmark_cmd(
    name: str = typer.Argument(..., help="Built-in model: contact or slip."),
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="OXT tar or extracted directory."
    ),
    task: str = typer.Option("", help="Task name; optional when the archive holds exactly one."),
    stream: str | None = typer.Option(
        None, help="Tactile stream name; optional when the task has one."
    ),
    window: int | None = typer.Option(
        None, min=1, help="Window frames; defaults to 1 for contact, 2 for slip."
    ),
    on_threshold: float | None = typer.Option(None, help="Contact: begin threshold."),
    off_threshold: float | None = typer.Option(None, help="Contact: end threshold."),
    micro_threshold: float | None = typer.Option(None, help="Slip: micro_slip threshold."),
    slip_threshold: float | None = typer.Option(None, help="Slip: slip threshold."),
    center: float | None = typer.Option(None, help="Logistic center for the score."),
    gain: float | None = typer.Option(None, help="Logistic gain for the score."),
    all_streams: bool = typer.Option(
        False, "--all-streams", help="Benchmark every tactile stream; nest the report per stream."
    ),
    out: Path | None = typer.Option(None, help="Write the JSON report to this path."),
    artifact: Path | None = typer.Option(
        None, "--artifact", help="ONNX scoring artifact; switches to the onnxruntime backend."
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Override the recorded model_id."),
) -> None:
    """Run a built-in model over every episode of a task; deterministic report."""
    params = _model_params(
        name, on_threshold, off_threshold, micro_threshold, slip_threshold, center, gain
    )
    if artifact is not None:
        # the logistic center/gain are baked into the artifact at export time
        params.pop("center", None)
        params.pop("gain", None)
    window_frames = window if window is not None else _default_window(name)
    try:
        with OpenXTactileArchive(source) as archive:
            resolved_task = _resolve_task(archive, task)
            task_obj = archive.open_task(resolved_task)
            episode_count = task_obj.info().episodes
            stream_keys = [s.stream for s in task_obj.streams()]
    except (KeyError, OSError, ValueError) as error:
        _fail(error)

    def run_stream(stream_key: str | None) -> dict[str, Any]:
        sensor_info: dict[str, Any] | None = None
        resolved_stream = stream_key or ""

        def make_model() -> Any:
            return _build_model(name, dict(params), artifact, model_id)

        def episode_streams() -> Iterator[tuple[int, Iterator[TactileObservation]]]:
            nonlocal sensor_info, resolved_stream
            for index in range(episode_count):
                adapter = _open_episode_adapter(source, resolved_task, index, stream_key, None)
                if sensor_info is None:
                    descriptor = adapter.descriptor()
                    sensor_info = to_debug_dict(descriptor)
                    resolved_stream = descriptor.frame_id
                try:
                    yield index, observations(adapter)
                finally:
                    adapter.close()

        report = benchmark_episodes(make_model, episode_streams(), window_frames=window_frames)
        report["task"] = resolved_task
        report["stream"] = resolved_stream
        report["sensor"] = sensor_info
        report["parameters"] = params
        return report

    if all_streams:
        report: dict[str, Any] = {
            "task": resolved_task,
            "runs": [run_stream(key) for key in stream_keys],
        }
        total_events = sum(run["totals"]["events"] for run in report["runs"])
        summary_counts: dict[str, int] = {}
        for run in report["runs"]:
            for kind, count in run["totals"]["counts"].items():
                summary_counts[kind] = summary_counts.get(kind, 0) + count
        totals = {
            "streams": len(report["runs"]),
            "episodes": sum(run["totals"]["episodes"] for run in report["runs"]),
            "frames": sum(run["totals"]["frames"] for run in report["runs"]),
            "events": total_events,
            "counts": summary_counts,
        }
    else:
        report = run_stream(stream)
        totals = report["totals"]
    payload = to_debug_json(report)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote report to {out}")
    else:
        typer.echo(payload)
    typer.echo(
        f"summary: {totals['episodes']} episodes, {totals['frames']} frames, "
        f"{totals['events']} events {totals['counts']} (window={window_frames})"
    )


if __name__ == "__main__":
    app()
