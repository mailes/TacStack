"""Phase 4 tests: capability validation, quality report, benchmark grouping."""

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from tacstack import SensorDescriptor, TactileObservation
from tacstack.adapters.open_x_tactile import OpenXTactileArchive
from tacstack.adapters.open_x_tactile.quality import assess_task
from tacstack.cli.main import app
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"

runner = CliRunner()


@pytest.fixture
def sensor() -> SensorDescriptor:
    return SensorDescriptor(
        "fixture", "test", "taxel", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
    )


def _observation(sensor: SensorDescriptor, index: int, value: float) -> TactileObservation:
    return TactileObservation(
        timestamp_ns=index * 1_000_000_000,
        sensor=sensor,
        raw=None,
        taxels=np.full((1, 6), value, dtype=np.float64),
        metadata={"oxt_frame_index": index},
    )


def test_runtime_rejects_sensor_without_intersecting_capabilities() -> None:
    # accepted = {tactile_image, taxel_force}: a temperature-only sensor has
    # an empty intersection and must be rejected before infer
    temperature_only = SensorDescriptor(
        "tmp", "test", "thermo", "temperature", "tmp", 30.0, frozenset({"temperature"})
    )
    taxel_sensor = SensorDescriptor(
        "tax", "test", "taxel", "taxel", "tax", 30.0, frozenset({"taxel_force"})
    )
    model = builtin_model("contact")
    Runtime(model, window_frames=1).process(_observation(taxel_sensor, 0, 0.9))
    with pytest.raises(ValueError, match="do not intersect"):
        Runtime(model, window_frames=1).process(_observation(temperature_only, 0, 0.9))


def test_runtime_manifest_all_of_check(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact")
    model._manifest = type(model._manifest)(
        model_id="strict",
        version="0.1.0",
        task="contact",
        required_capabilities=frozenset({"shear_force"}),
        window_ms=100,
        runtime="builtin",
        artifact_uri="builtin://strict",
    )
    with pytest.raises(ValueError, match="missing required capabilities"):
        Runtime(model, window_frames=1).process(_observation(sensor, 0, 0.9))


def test_capability_check_runs_once_per_stream(sensor: SensorDescriptor) -> None:
    runtime = Runtime(builtin_model("contact"), window_frames=1)
    runtime.process(_observation(sensor, 0, 0.9))
    runtime.process(_observation(sensor, 1, 0.9))
    assert runtime._validated_sensors == {"fixture"}


def test_assess_task_reports_clean_fixture() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        task = archive.open_task("Wipe_Demo")
        report = assess_task(task)
    assert report["task"] == "Wipe_Demo"
    assert report["episodes"] == 3 and report["frames"] == 40
    assert report["episode_length"] == {"min": 10, "max": 15, "mean": 40 / 3}
    assert report["timestamps"]["monotonic"] is True
    assert report["timestamps"]["unique_steps"] == [1]
    for stream in report["streams"]:
        assert stream["nonfinite"] == 0
        assert stream["frames_scanned"] == 40


def test_assess_task_respects_max_frames() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        report = assess_task(archive.open_task("Wipe_Demo"), max_frames=5)
    for stream in report["streams"]:
        assert stream["frames_scanned"] == 5
    assert report["scanned_frames"] == 5


def test_dataset_quality_cli() -> None:
    result = runner.invoke(
        app, ["dataset", "quality", str(FIXTURE), "--task", "Wipe_Demo", "--max-frames", "10"]
    )
    assert result.exit_code == 0, result.output
    assert "timestamps_monotonic=True" in result.output
    assert "right_gripper:0 nonfinite" in result.output


def test_benchmark_all_streams_groups_report(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "contact",
            str(FIXTURE),
            "--task",
            "task_0001_Pick_Demo",
            "--all-streams",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json_loads(out.read_text())
    assert report["task"] == "task_0001_Pick_Demo"
    streams = [run["stream"] for run in report["runs"]]
    assert streams == ["right_gripper", "right_grippertorque"]
    for run in report["runs"]:
        assert run["sensor"]["vendor"] == "Open-X-Tactile"
        assert run["totals"]["episodes"] == 2


def test_benchmark_fresh_model_per_episode(tmp_path: Path) -> None:
    # every Wipe episode starts with a high-activity frame; with fresh model
    # state each episode must emit its own contact_begin
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "contact",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--stream",
            "right_gripper",
            "--on-threshold",
            "0.45",
            "--off-threshold",
            "0.3",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text())
    begins = sum(episode["counts"].get("contact_begin", 0) for episode in report["episodes"])
    assert begins == 3  # one per episode, not suppressed by earlier episodes


def json_loads(text: str):
    return json.loads(text)
