"""Open-X-Tactile adapter tests against the golden fixture and synthetic stores."""

import tarfile
from pathlib import Path

import numpy as np
import pytest
import zarr

from tacstack.adapters.open_x_tactile import (
    OpenXTactileAdapter,
    OpenXTactileArchive,
    TactileStreamInfo,
)
from tacstack.adapters.open_x_tactile.archive import OpenXTactileTask

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"


def iterate(adapter: OpenXTactileAdapter) -> list:
    adapter.open()
    try:
        frames = []
        while True:
            try:
                frames.append(adapter.read())
            except EOFError:
                return frames
    finally:
        adapter.close()


def test_archive_lists_task_and_streams() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        assert archive.task_names() == ["Wipe_Demo", "task_0001_Pick_Demo"]
        info = archive.open_task("Wipe_Demo").info()
    assert info.episodes == 3
    assert info.frames == 40
    assert "timestamps" in info.arrays
    assert info.streams == (
        TactileStreamInfo(
            stream="right_gripper",
            data_key="right_tactile_data_gripper",
            sensor="GelSightMini",
            kind="image",
            areas=2,
        ),
    )


def test_archive_lists_taxel_task() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        info = archive.open_task("task_0001_Pick_Demo").info()
    assert info.episodes == 2
    assert info.frames == 20
    assert info.streams == (
        TactileStreamInfo(
            stream="left_fingertip",
            data_key="left_tactile_data_fingertip",
            sensor="uSkin",
            kind="state",
            areas=2,
        ),
    )


def test_adapter_replays_taxel_stream() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="task_0001_Pick_Demo", episode=1)
    frames = iterate(adapter)
    assert len(frames) == 12
    first = frames[0]
    assert first.taxels is not None
    assert first.taxels.shape == (2, 16, 3)
    assert first.taxels.dtype == np.float32
    assert first.tactile_image is None
    assert first.raw["right_hand_pose"].shape == (1, 6)
    assert first.metadata["oxt_tactile_type"] == "state"
    assert first.metadata["oxt_tactile_areas"] == (0, 1)
    descriptor = adapter.descriptor()
    assert descriptor.sensor_id == "oxt:task_0001_Pick_Demo:left_fingertip"
    assert descriptor.model == "uSkin"
    assert descriptor.modality == "taxel"
    assert descriptor.capabilities == frozenset({"taxel_force"})


def test_adapter_iterates_first_episode() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0)
    frames = iterate(adapter)
    assert len(frames) == 10
    timestamps = [frame.timestamp_ns for frame in frames]
    assert timestamps == [index * 1_000_000_000 for index in range(10)]
    assert all(type(frame.timestamp_ns) is int for frame in frames)


def test_adapter_episode_slice_and_frame_indices() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=2)
    frames = iterate(adapter)
    assert len(frames) == 15
    assert [frame.metadata["oxt_frame_index"] for frame in frames[:3]] == [25, 26, 27]


def test_adapter_maps_tactile_payload_raw_and_metadata() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0)
    adapter.open()
    try:
        first = adapter.read()
    finally:
        adapter.close()
    assert first.tactile_image is not None
    assert first.tactile_image.shape == (2, 32, 32, 3)
    assert first.tactile_image.dtype == np.uint8
    assert first.taxels is None
    assert first.raw["right_arm_joints"].shape == (7,)
    assert first.raw["sub_task_instruction"] == "wipe the table"
    assert "camera_main_rgb" not in first.raw
    assert first.metadata["oxt_camera_streams"] == ("camera_main_rgb",)
    assert first.metadata["oxt_stream"] == "right_gripper"
    assert first.metadata["oxt_tactile_areas"] == (0, 1)
    assert first.metadata["oxt_timestamp_domain"] == "frame_index"
    assert first.calibration_id is None


def test_adapter_descriptor() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0)
    adapter.open()
    try:
        descriptor = adapter.descriptor()
    finally:
        adapter.close()
    assert descriptor.sensor_id == "oxt:Wipe_Demo:right_gripper"
    assert descriptor.vendor == "Open-X-Tactile"
    assert descriptor.model == "GelSightMini"
    assert descriptor.modality == "vision_tactile"
    assert descriptor.capabilities == frozenset({"tactile_image"})
    assert descriptor.sample_rate_hz is None


def test_adapter_rate_hz_converts_timestamps() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0, rate_hz=30.0)
    frames = iterate(adapter)
    timestamps = [frame.timestamp_ns for frame in frames]
    assert timestamps[1] == round(1_000_000_000 / 30)
    assert timestamps == sorted(timestamps)
    assert adapter.descriptor().sample_rate_hz == 30.0


def test_adapter_explicit_stream_selection() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0, stream="right_gripper")
    assert len(iterate(adapter)) == 10


def test_adapter_rejects_unknown_task_and_episode() -> None:
    with pytest.raises(KeyError):
        OpenXTactileAdapter(FIXTURE, task="Missing").open()
    with pytest.raises(IndexError):
        OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=7).open()


def test_adapter_requires_open() -> None:
    adapter = OpenXTactileAdapter(FIXTURE, task="Wipe_Demo", episode=0)
    with pytest.raises(RuntimeError):
        adapter.read()
    with pytest.raises(RuntimeError):
        adapter.descriptor()


def build_two_stream_store(root: Path) -> Path:
    """Synthetic directory source with one state stream and one image stream."""
    store_root = root / "TwoStreams.zarr"
    total = 6

    def put(name: str, data: np.ndarray, chunks: tuple[int, ...]) -> None:
        zarr.create_array(store=store_root, name=name, data=data, chunks=chunks, zarr_format=2)

    put("meta/episode_ends", np.array([2, 6], dtype="<i8"), (2,))
    put("data/timestamps", np.arange(total, dtype="<i8"), (3,))
    put("data/left_tactile_data_pad", np.arange(total * 4, dtype="<f4").reshape(total, 4), (3, 4))
    put("data/left_tactile_sensor_pad", np.full(total, "uSkin", dtype="<U5"), (3,))
    put("data/left_tactile_type_pad", np.full(total, "state", dtype="<U5"), (3,))
    put("data/right_tactile_data_pad", np.zeros((total, 1, 8, 8, 3), dtype="u1"), (3, 1, 8, 8, 3))
    put("data/right_tactile_sensor_pad", np.full(total, "GelSightMini", dtype="<U12"), (3,))
    put("data/right_tactile_type_pad", np.full(total, "image", dtype="<U5"), (3,))
    return root


def test_directory_source_with_two_streams(tmp_path: Path) -> None:
    source = build_two_stream_store(tmp_path)
    with OpenXTactileArchive(source) as archive:
        assert archive.task_names() == ["TwoStreams"]
        task = archive.open_task("TwoStreams")
        assert sorted(stream.stream for stream in task.streams()) == ["left_pad", "right_pad"]


def test_adapter_ambiguous_stream_requires_choice(tmp_path: Path) -> None:
    source = build_two_stream_store(tmp_path)
    with pytest.raises(ValueError, match="multiple streams"):
        OpenXTactileAdapter(source, task="TwoStreams", episode=0).open()
    state = OpenXTactileAdapter(source, task="TwoStreams", episode=1, stream="left_pad")
    frames = iterate(state)
    assert len(frames) == 4
    assert frames[0].taxels is not None
    assert frames[0].taxels.shape == (4,)
    assert frames[0].tactile_image is None
    assert state.descriptor().modality == "taxel"
    assert state.descriptor().capabilities == frozenset({"taxel_force"})
    image = OpenXTactileAdapter(source, task="TwoStreams", episode=1, stream="right_pad")
    frames = iterate(image)
    assert frames[0].tactile_image.shape == (1, 8, 8, 3)


def test_extracted_directory_source_matches_tar(tmp_path: Path) -> None:
    extracted = tmp_path / "dataset"
    extracted.mkdir()
    with tarfile.open(FIXTURE) as tf:
        tf.extractall(extracted, filter="data")
    source = extracted / "TacStackDemo"
    with OpenXTactileArchive(source) as archive:
        assert archive.task_names() == ["Wipe_Demo", "task_0001_Pick_Demo"]
        frames = iterate(OpenXTactileAdapter(source, task="Wipe_Demo", episode=1))
    assert len(frames) == 15


def test_task_caches_arrays() -> None:
    with OpenXTactileArchive(FIXTURE) as archive:
        task: OpenXTactileTask = archive.open_task("Wipe_Demo")
        assert task.array("meta/episode_ends") is task.array("meta/episode_ends")
