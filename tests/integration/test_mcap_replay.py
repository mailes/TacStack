"""MCAP replay adapter tests: round trip, stream filter, summaries mode."""

import itertools
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from tacstack.adapters.base import observations
from tacstack.adapters.mcap import McapReplayAdapter
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter
from tacstack.cli.main import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"

runner = CliRunner()


def _convert(tmp_path: Path, *, embed: bool, episode: int = 0) -> Path:
    out = tmp_path / "episode.mcap"
    args = [
        "dataset",
        "convert",
        str(FIXTURE),
        "--task",
        "Wipe_Demo",
        "--episode",
        str(episode),
        "--stream",
        "right_gripper",
        "--out",
        str(out),
    ]
    if embed:
        args.append("--embed")
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return out


def test_embedded_round_trip_matches_source(tmp_path: Path) -> None:
    recording = _convert(tmp_path, embed=True)
    source = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0, stream="right_gripper")
    source.open()
    replay = McapReplayAdapter(recording)
    replay.open()
    try:
        for expected in observations(source):
            actual = replay.read()
            assert actual.timestamp_ns == expected.timestamp_ns
            assert actual.sensor.sensor_id == expected.sensor.sensor_id
            assert actual.sensor.capabilities == expected.sensor.capabilities
            assert actual.tactile_image is not None
            np.testing.assert_array_equal(actual.tactile_image, expected.tactile_image)
            assert actual.metadata["oxt_frame_index"] == expected.metadata["oxt_frame_index"]
            np.testing.assert_array_equal(
                np.asarray(actual.raw["right_arm_joints"]),
                np.asarray(expected.raw["right_arm_joints"]),
            )
        with pytest.raises(EOFError):
            replay.read()
    finally:
        source.close()
        replay.close()


def test_summarized_replay_carries_summaries(tmp_path: Path) -> None:
    recording = _convert(tmp_path, embed=False)
    replay = McapReplayAdapter(recording)
    replay.open()
    try:
        observation = replay.read()
        assert observation.taxels is None and observation.tactile_image is None
        summaries = observation.metadata["replay_summaries"]
        assert summaries["tactile_image"]["shape"] == [2, 32, 32, 3]
        assert summaries["tactile_image"]["nonfinite"] == 0
    finally:
        replay.close()


def test_multi_stream_recording_selects_stream(tmp_path: Path) -> None:
    from tacstack.integrations.mcap import write_episode_mcap

    adapters = []
    streams = []
    try:
        for stream in ("right_gripper", "right_grippertorque"):
            adapter = OpenXTactileAdapter(
                FIXTURE, task="task_0001_Pick_Demo", episode=0, stream=stream
            )
            adapter.open()
            adapters.append(adapter)
            streams.append(observations(adapter))
        out = tmp_path / "multi.mcap"
        summary = write_episode_mcap(itertools.chain(*streams), out, embed_payloads=True)
        assert summary.messages == 16
    finally:
        for adapter in adapters:
            adapter.close()

    first = McapReplayAdapter(out)
    first.open()
    try:
        observation = first.read()  # no stream filter: first stream in the file wins
        assert observation.sensor.sensor_id.endswith("right_gripper")
    finally:
        first.close()

    second = McapReplayAdapter(out, stream="oxt:task_0001_Pick_Demo:right_grippertorque")
    second.open()
    try:
        observation = second.read()
        assert observation.sensor.sensor_id.endswith("right_grippertorque")
        assert observation.taxels is not None and observation.taxels.shape == (1, 6)
    finally:
        second.close()


def test_replay_cli_accepts_mcap(tmp_path: Path) -> None:
    recording = _convert(tmp_path, embed=True)
    out = tmp_path / "replay.rrd"
    result = runner.invoke(app, ["replay", str(recording), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "logged 10 observations to rerun" in result.output


def test_replay_cli_with_model_logs_events(tmp_path: Path) -> None:
    recording = _convert(tmp_path, embed=True)
    out = tmp_path / "replay.rrd"
    result = runner.invoke(app, ["replay", str(recording), "--model", "contact", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "and" in result.output
    assert "model events" in result.output


def test_model_run_accepts_mcap_source(tmp_path: Path) -> None:
    recording = _convert(tmp_path, embed=True)
    result = runner.invoke(app, ["model", "run", "contact", str(recording)])
    assert result.exit_code == 0, result.output
    assert "summary: 10 frames," in result.output
