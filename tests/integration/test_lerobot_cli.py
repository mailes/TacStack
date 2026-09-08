"""CLI integration tests: a LeRobot v3.0 dataset directory replays through
the same model-run path as OXT archives and MCAP recordings."""

import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from tacstack.cli.main import app
from tacstack.core import SensorDescriptor, TactileObservation
from tacstack.integrations.lerobot import LeRobotDatasetWriter

runner = CliRunner()


def _descriptor() -> SensorDescriptor:
    return SensorDescriptor(
        sensor_id="synthetic:tactile",
        vendor="synthetic",
        model="matrix-16",
        modality="taxel",
        frame_id="tactile",
        sample_rate_hz=30.0,
        capabilities=frozenset({"taxel_force"}),
    )


def _write_dataset(root: Path) -> None:
    writer = LeRobotDatasetWriter(root, fps=30)
    values_by_frame = [np.full(16, 0.1, dtype=np.float32) for _ in range(3)] + [
        np.full(16, 0.9, dtype=np.float32) for _ in range(5)
    ]
    frames = [
        TactileObservation(
            timestamp_ns=i * 33_333_333,
            sensor=_descriptor(),
            raw=values,
            taxels=values,
        )
        for i, values in enumerate(values_by_frame)
    ]
    writer.add_episode(frames, task="grasp")
    writer.finalize()


def test_model_run_reads_lerobot_dataset(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_dataset(root)
    result = runner.invoke(app, ["model", "run", "contact", str(root)])
    assert result.exit_code == 0, result.output
    event_lines = [line for line in result.output.splitlines() if line.startswith("{")]
    events = [json.loads(line) for line in event_lines]
    assert events, "the synthetic grasp should cross the contact threshold"
    assert any(event["kind"] == "contact_begin" for event in events)
    assert all(event["sensor_id"] == "lerobot:ds:observation.tactile" for event in events)


def test_model_run_rejects_directory_without_info_json(tmp_path: Path) -> None:
    empty = tmp_path / "not-a-dataset"
    empty.mkdir()
    result = runner.invoke(app, ["model", "run", "contact", str(empty)])
    assert result.exit_code != 0
