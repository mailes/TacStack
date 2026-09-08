from pathlib import Path

import numpy as np
import pytest

from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter
from tacstack.integrations.rerun import RerunReplay

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"


def _replay_to(path: Path, task: str, stream: str, *, episode: int = 0) -> int:
    adapter = OpenXTactileAdapter(FIXTURE, task=task, episode=episode, stream=stream)
    adapter.open()
    replay = RerunReplay()
    replay.save(path)
    count = 0
    try:
        for observation in observations(adapter):
            replay.log_observation(observation)
            count += 1
    finally:
        adapter.close()
        replay.flush()
    return count


def test_replays_image_stream_to_rrd(tmp_path: Path) -> None:
    out = tmp_path / "image.rrd"
    assert _replay_to(out, "Wipe_Demo", "right_gripper") == 10
    assert out.stat().st_size > 0


def test_replays_later_episode_large_timestamps(tmp_path: Path) -> None:
    # episode 1 covers frames 8..20, so timestamp_ns reaches 2e10; this
    # regression-tests the rerun duration overflow at int64 boundary
    out = tmp_path / "later.rrd"
    assert _replay_to(out, "task_0001_Pick_Demo", "right_grippertorque", episode=1) == 12
    assert out.stat().st_size > 0


def test_replays_taxel_matrix_stream_to_rrd(tmp_path: Path) -> None:
    out = tmp_path / "matrix.rrd"
    assert _replay_to(out, "task_0001_Pick_Demo", "right_gripper") == 8
    assert out.stat().st_size > 0


def test_replays_force_torque_stream_to_rrd(tmp_path: Path) -> None:
    out = tmp_path / "ft.rrd"
    assert _replay_to(out, "task_0001_Pick_Demo", "right_grippertorque") == 8
    assert out.stat().st_size > 0


def test_one_recording_holds_multiple_streams(tmp_path: Path) -> None:
    out = tmp_path / "multi.rrd"
    replay = RerunReplay()
    replay.save(out)
    count = 0
    for task, stream in (
        ("Wipe_Demo", "right_gripper"),
        ("task_0001_Pick_Demo", "right_grippertorque"),
    ):
        adapter = OpenXTactileAdapter(FIXTURE, task=task, episode=0, stream=stream)
        adapter.open()
        try:
            for observation in observations(adapter):
                replay.log_observation(observation)
                count += 1
        finally:
            adapter.close()
    replay.flush()
    assert count == 18
    assert out.stat().st_size > 0


def test_replays_opted_in_camera_frames(tmp_path: Path) -> None:
    adapter = OpenXTactileAdapter(
        FIXTURE,
        task="task_0001_Pick_Demo",
        episode=0,
        stream="right_grippertorque",
        extra_arrays=("right_wrist_camera_rgb",),
    )
    adapter.open()
    try:
        first = adapter.read()
    finally:
        adapter.close()
    assert first.raw["right_wrist_camera_rgb"].shape == (32, 32, 3)
    out = tmp_path / "camera.rrd"
    replay = RerunReplay()
    replay.save(out)
    replay.log_observation(first)
    replay.flush()
    assert out.stat().st_size > 0


def test_extra_array_must_exist() -> None:
    adapter = OpenXTactileAdapter(
        FIXTURE, task="Wipe_Demo", stream="right_gripper", extra_arrays=("nope",)
    )
    with pytest.raises(KeyError, match="extra arrays not found"):
        adapter.open()


def test_extra_array_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        OpenXTactileAdapter(
            FIXTURE,
            task="Wipe_Demo",
            stream="right_gripper",
            extra_arrays=("right_arm_joints", "right_arm_joints"),
        )


def test_extra_arrays_embed_non_camera_arrays() -> None:
    adapter = OpenXTactileAdapter(
        FIXTURE,
        task="Wipe_Demo",
        episode=0,
        stream="right_gripper",
        extra_arrays=("camera_main_rgb",),
    )
    adapter.open()
    try:
        observation = adapter.read()
    finally:
        adapter.close()
    assert observation.raw["camera_main_rgb"].shape == (32, 32, 3)
    assert observation.metadata["oxt_camera_streams"] == ("camera_main_rgb",)
    assert observation.raw["camera_main_rgb"].dtype == np.uint8
