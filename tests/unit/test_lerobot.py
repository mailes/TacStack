"""LeRobot interop tests: v3.0 export layout, replay round-trip, feature
selection and validation (synthetic taxel streams, no LeRobot dependency)."""

import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from tacstack.adapters.base import observations
from tacstack.adapters.lerobot import LeRobotAdapter
from tacstack.core import SensorDescriptor, TactileObservation
from tacstack.integrations.lerobot import (
    LeRobotDatasetWriter,
    load_lerobot_info,
    resolve_tactile_feature,
)

TAXEL_COUNT = 16


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


def _observations(frames: int) -> Iterator[TactileObservation]:
    for i in range(frames):
        values = np.arange(TAXEL_COUNT, dtype=np.float32) + i
        yield TactileObservation(
            timestamp_ns=i * 33_333_333,
            sensor=_descriptor(),
            raw=values,
            taxels=values,
        )


def _write_dataset(root: Path) -> None:
    writer = LeRobotDatasetWriter(root, fps=30)
    writer.add_episode(_observations(5))
    writer.add_episode(_observations(5), task="wipe")
    writer.finalize()


# --- export layout pinned against LeRobot v3.0 ------------------------------


def test_export_layout_matches_v30(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_dataset(root)
    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    assert info["codebase_version"] == "v3.0"
    assert info["fps"] == 30
    assert info["total_episodes"] == 2
    assert info["total_frames"] == 10
    assert info["total_tasks"] == 2
    assert info["data_path"] == "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
    assert info["features"]["observation.tactile"] == {
        "dtype": "float32",
        "shape": [TAXEL_COUNT],
        "names": None,
    }
    assert info["features"]["timestamp"] == {"dtype": "float32", "shape": [1], "names": None}
    assert (root / "data" / "chunk-000" / "file-000.parquet").is_file()
    assert (root / "data" / "chunk-000" / "file-001.parquet").is_file()
    assert (root / "meta" / "episodes" / "chunk-000" / "file-000.parquet").is_file()
    assert (root / "meta" / "tasks.parquet").is_file()
    assert (root / "meta" / "stats.json").is_file()


def test_export_parquet_columns_and_types(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "ds"
    _write_dataset(root)
    table = pq.read_table(root / "data" / "chunk-000" / "file-000.parquet")
    assert set(table.column_names) == {
        "frame_index",
        "timestamp",
        "episode_index",
        "index",
        "task_index",
        "observation.tactile",
    }
    assert table.schema.field("observation.tactile").type == pa.list_(pa.float32())
    assert table.column("timestamp").to_pylist() == pytest.approx([i / 30 for i in range(5)])
    assert table.column("frame_index").to_pylist() == [0, 1, 2, 3, 4]
    assert table.column("episode_index").to_pylist() == [0] * 5
    second = pq.read_table(root / "data" / "chunk-000" / "file-001.parquet")
    assert second.column("index").to_pylist() == [5, 6, 7, 8, 9]
    assert second.column("task_index").to_pylist() == [1] * 5


def test_export_tasks_and_stats(tmp_path: Path) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "ds"
    _write_dataset(root)
    tasks = pq.read_table(root / "meta" / "tasks.parquet")
    assert tasks.column("task").to_pylist() == ["tacstack export", "wipe"]
    stats = json.loads((root / "meta" / "stats.json").read_text(encoding="utf-8"))
    payload = stats["observation.tactile"]
    assert payload["count"] == 10
    assert payload["min"] == list(range(TAXEL_COUNT))
    assert payload["max"] == [value + 4 for value in range(TAXEL_COUNT)]
    timestamp = stats["timestamp"]
    assert timestamp["count"] == 10
    assert len(timestamp["min"]) == 1


# --- replay round-trip --------------------------------------------------------


def test_round_trip_preserves_payload_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_dataset(root)
    adapter = LeRobotAdapter(root)
    adapter.open()
    sensor = adapter.descriptor()
    assert sensor.sensor_id == "lerobot:ds:observation.tactile"
    assert sensor.vendor == "LeRobot"
    assert sensor.modality == "taxel"
    assert sensor.frame_id == "observation.tactile"
    assert sensor.sample_rate_hz == 30.0
    assert sensor.capabilities == frozenset({"taxel_force"})

    replayed = list(observations(adapter))
    assert len(replayed) == 10
    for i, observation in enumerate(replayed):
        episode, frame = divmod(i, 5)
        expected = np.arange(TAXEL_COUNT, dtype=np.float32) + frame
        expected_task = "tacstack export" if episode == 0 else "wipe"
        assert np.array_equal(observation.taxels, expected)
        assert observation.taxels is not None and observation.taxels.dtype == np.float32
        assert observation.metadata["episode_index"] == episode
        assert observation.metadata["frame_index"] == frame
        assert observation.metadata["index"] == i
        assert observation.metadata["task"] == expected_task
        assert observation.metadata["timestamp"] == pytest.approx(frame / 30)
        assert observation.timestamp_ns == int(round(frame * 1_000_000_000 / 30))
    with pytest.raises(EOFError):
        adapter.read()


def test_episode_filter(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_dataset(root)
    adapter = LeRobotAdapter(root, episode=1)
    adapter.open()
    replayed = list(observations(adapter))
    assert len(replayed) == 5
    assert all(observation.metadata["episode_index"] == 1 for observation in replayed)


def test_float64_dtype_passthrough(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "ds"
    writer = LeRobotDatasetWriter(root, fps=10)
    values = np.linspace(-1.0, 1.0, 8, dtype=np.float64)
    writer.add_episode(
        TactileObservation(timestamp_ns=0, sensor=_descriptor(), raw=values, taxels=values)
        for _ in range(1)
    )
    writer.finalize()
    info = load_lerobot_info(root)
    assert info["features"]["observation.tactile"]["dtype"] == "float64"
    table = pq.read_table(root / "data" / "chunk-000" / "file-000.parquet")
    assert table.schema.field("observation.tactile").type == pa.list_(pa.float64())
    adapter = LeRobotAdapter(root)
    adapter.open()
    replayed = list(observations(adapter))
    assert np.array_equal(replayed[0].taxels, values)


# --- reader validation --------------------------------------------------------


def test_reader_rejects_v21_dataset(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_dataset(root)
    info_file = root / "meta" / "info.json"
    info = json.loads(info_file.read_text(encoding="utf-8"))
    info["codebase_version"] = "v2.1"
    info_file.write_text(json.dumps(info), encoding="utf-8")
    adapter = LeRobotAdapter(root)
    with pytest.raises(ValueError, match="v2.1"):
        adapter.open()


def test_reader_requires_dataset_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LeRobotAdapter(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    adapter = LeRobotAdapter(empty)
    with pytest.raises(FileNotFoundError, match="info.json"):
        adapter.open()


def test_reader_requires_open(tmp_path: Path) -> None:
    adapter = LeRobotAdapter(tmp_path)
    with pytest.raises(RuntimeError, match="open()"):
        adapter.read()


def test_reader_reads_hand_built_2d_feature(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "hand"
    (root / "meta").mkdir(parents=True)
    (root / "data" / "chunk-000").mkdir(parents=True)
    info = {
        "codebase_version": "v3.0",
        "fps": 10,
        "features": {
            "observation.tactile": {
                "dtype": "float32",
                "shape": [4, 4],
                "names": None,
            }
        },
        "total_episodes": 1,
        "total_frames": 3,
        "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
    }
    (root / "meta" / "info.json").write_text(json.dumps(info), encoding="utf-8")
    frames = np.arange(3 * 16, dtype=np.float32).reshape(3, 4, 4)
    table = pa.Table.from_pydict(
        {
            "observation.tactile": pa.array(
                [frames[i].tolist() for i in range(3)],
                type=pa.list_(pa.list_(pa.float32(), 4), 4),
            ),
            "frame_index": pa.array([0, 1, 2], type=pa.int64()),
            "timestamp": pa.array([0.0, 0.1, 0.2], type=pa.float32()),
            "episode_index": pa.array([0, 0, 0], type=pa.int64()),
            "index": pa.array([0, 1, 2], type=pa.int64()),
            "task_index": pa.array([0, 0, 0], type=pa.int64()),
        }
    )
    pq.write_table(table, root / "data" / "chunk-000" / "file-000.parquet", compression="snappy")
    adapter = LeRobotAdapter(root)
    adapter.open()
    replayed = list(observations(adapter))
    assert len(replayed) == 3
    for i, observation in enumerate(replayed):
        assert observation.taxels is not None
        assert observation.taxels.shape == (4, 4)
        assert np.array_equal(observation.taxels, frames[i])


# --- feature selection ---------------------------------------------------------


TACTILE_SPEC = {"dtype": "float32", "shape": [16], "names": None}


def test_feature_resolution_prefers_tactile_named_candidates() -> None:
    features = {
        "observation.state": {"dtype": "float32", "shape": [7], "names": None},
        "observation.tactile": TACTILE_SPEC,
    }
    assert resolve_tactile_feature(features) == "observation.tactile"
    assert resolve_tactile_feature(features, "observation.state") == "observation.state"
    assert resolve_tactile_feature({"observation.tactile": TACTILE_SPEC}) == "observation.tactile"


def test_feature_resolution_errors() -> None:
    two_tactile = {
        "observation.tactile.left": TACTILE_SPEC,
        "observation.tactile.right": TACTILE_SPEC,
    }
    with pytest.raises(ValueError, match="cannot pick a tactile feature"):
        resolve_tactile_feature(two_tactile)
    with pytest.raises(ValueError, match="not an observation"):
        resolve_tactile_feature({"observation.tactile": TACTILE_SPEC}, "action")
    with pytest.raises(ValueError, match="cannot pick"):
        resolve_tactile_feature(
            {"observation.images.cam": {"dtype": "video", "shape": [], "names": None}}
        )


# --- writer validation ----------------------------------------------------------


def test_writer_rejects_image_and_2d_payloads(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    writer = LeRobotDatasetWriter(root, fps=30)
    image = TactileObservation(
        timestamp_ns=0,
        sensor=_descriptor(),
        raw=None,
        tactile_image=np.zeros((4, 4, 3), dtype=np.uint8),
    )
    with pytest.raises(ValueError, match="MCAP embed"):
        writer.add_episode([image])
    writer2 = LeRobotDatasetWriter(tmp_path / "ds2", fps=30)
    matrix = TactileObservation(
        timestamp_ns=0,
        sensor=_descriptor(),
        raw=None,
        taxels=np.zeros((4, 4), dtype=np.float32),
    )
    with pytest.raises(ValueError, match="1-D"):
        writer2.add_episode([matrix])


def test_writer_rejects_empty_stream_and_mismatched_frames(tmp_path: Path) -> None:
    writer = LeRobotDatasetWriter(tmp_path / "ds", fps=30)
    with pytest.raises(ValueError, match="empty"):
        writer.add_episode([])
    values = np.arange(TAXEL_COUNT, dtype=np.float32)
    writer.add_episode(
        [TactileObservation(timestamp_ns=0, sensor=_descriptor(), raw=values, taxels=values)]
    )
    other = np.arange(TAXEL_COUNT + 1, dtype=np.float32)
    with pytest.raises(ValueError, match="payload mismatch"):
        writer.add_episode(
            [TactileObservation(timestamp_ns=1, sensor=_descriptor(), raw=other, taxels=other)]
        )


def test_writer_rejects_bad_fps(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fps"):
        LeRobotDatasetWriter(tmp_path / "ds", fps=0)
