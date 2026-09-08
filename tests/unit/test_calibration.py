"""Phase 4 calibration-chain tests: adapter to observation to event to MCAP."""

from pathlib import Path

import numpy as np
import pytest
import zarr
from typer.testing import CliRunner

from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter, OpenXTactileArchive
from tacstack.adapters.open_x_tactile.quality import assess_task
from tacstack.cli.main import app
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"

runner = CliRunner()


def _build_task_dir(root: Path, timestamps: list[int]) -> Path:
    """Minimal one-stream task zarr with the given timestamp vector."""
    store = root / "Demo.zarr"

    def put(name: str, data: np.ndarray, chunks: tuple[int, ...]) -> None:
        zarr.create_array(
            store=store, name=name, data=data, chunks=chunks, zarr_format=2, compressors=None
        )

    total = len(timestamps)
    put("meta/episode_ends", np.array([total], dtype="<i8"), (1,))
    put("data/timestamps", np.array(timestamps, dtype="<i8"), (max(1, total),))
    put(
        "data/left_tactile_data_tip",
        np.ones((total, 1, 3), dtype="<f4"),
        (max(1, total), 1, 3),
    )
    put("data/left_tactile_area_tip", np.zeros((total, 1), dtype="<i8"), (max(1, total), 1))
    put("data/left_tactile_sensor_tip", np.full(total, "TestArray", dtype="<U9"), (max(1, total),))
    put("data/left_tactile_type_tip", np.full(total, "state", dtype="<U5"), (max(1, total),))
    return store


def test_calibration_id_flows_to_observation(tmp_path: Path) -> None:
    task_dir = _build_task_dir(tmp_path, [0, 1, 2, 5])
    adapter = OpenXTactileAdapter(
        task_dir.parent, task="Demo", episode=0, stream="left_tip", calibration_id="cal-2026-09"
    )
    adapter.open()
    try:
        observation = adapter.read()
    finally:
        adapter.close()
    assert observation.calibration_id == "cal-2026-09"


def test_calibration_id_rejects_blank() -> None:
    with pytest.raises(ValueError, match="calibration_id must not be empty"):
        OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", calibration_id="   ")


def test_calibration_id_flows_into_event_metadata(tmp_path: Path) -> None:
    task_dir = _build_task_dir(tmp_path, [0, 1, 2, 5])
    adapter = OpenXTactileAdapter(
        task_dir.parent, task="Demo", episode=0, stream="left_tip", calibration_id="cal-1"
    )
    model = builtin_model("contact", on_threshold=0.5, off_threshold=0.2, center=0.1, gain=10.0)
    runtime = Runtime(model, window_frames=1)
    adapter.open()
    calibration_seen: list = []
    try:
        for observation in observations(adapter):
            for event in runtime.process(observation):
                calibration_seen.append(event.metadata["calibration_id"])
    finally:
        adapter.close()
    assert calibration_seen and all(c == "cal-1" for c in calibration_seen)


def test_quality_detects_suspected_gap(tmp_path: Path) -> None:
    task_dir = _build_task_dir(tmp_path, [0, 1, 2, 10])
    with OpenXTactileArchive(task_dir.parent) as archive:
        report = assess_task(archive.open_task("Demo"))
    assert report["timestamps"]["monotonic"] is True
    assert report["timestamps"]["suspected_gaps"] == 1
    assert report["timestamps"]["steps"]["median"] == 1.0
    assert report["timestamps"]["steps"]["max"] == 8


def test_quality_report_no_gaps_on_fixture() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        report = assess_task(archive.open_task("Wipe_Demo"))
    assert report["timestamps"]["suspected_gaps"] == 0
    assert report["timestamps"]["steps"] == {"min": 1, "max": 1, "median": 1.0, "std": 0.0}


def test_calibration_round_trips_through_mcap(tmp_path: Path) -> None:
    recording = tmp_path / "marked.mcap"
    result = runner.invoke(
        app,
        [
            "dataset",
            "convert",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--stream",
            "right_gripper",
            "--calibration-id",
            "cal-2026-09",
            "--embed",
            "--out",
            str(recording),
        ],
    )
    assert result.exit_code == 0, result.output
    from tacstack.adapters.base import observations
    from tacstack.adapters.mcap import McapReplayAdapter

    replay = McapReplayAdapter(recording)
    replay.open()
    try:
        calibration_ids = {observation.calibration_id for observation in observations(replay)}
    finally:
        replay.close()
    assert calibration_ids == {"cal-2026-09"}
