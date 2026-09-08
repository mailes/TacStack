"""LeRobot dataset export: write TacStack observation streams as LeRobot
v3.0 dataset directories that the LeRobot tooling reads natively.

Contract (pinned against huggingface/lerobot ``CODEBASE_VERSION = "v3.0"``):
- layout: ``meta/info.json``, ``meta/stats.json``, ``meta/tasks.parquet``,
  ``meta/episodes/chunk-XXX/file-XXX.parquet`` and one data parquet per
  episode under the ``data_path`` template (LeRobot merges files by size on
  its own writes; one episode per file is a valid instantiation here).
- ``info.json``: only ``codebase_version``, ``fps`` and ``features`` are
  required by LeRobot; totals, chunk size, file-size caps and path templates
  are written with the LeRobot defaults. Feature ``shape`` is a JSON list.
- per-frame columns: ``frame_index`` (int64, episode-relative), ``timestamp``
  (float32 = frame_index / fps), ``episode_index`` / ``index`` (global int64)
  / ``task_index``, plus the payload feature.
- the tactile payload is a 1-D array column stored as Arrow ``list<T>`` with
  the array's own numpy dtype string (raw-first: float32 stays float32,
  float64 stays float64), which is how LeRobot represents 1-D features
  (``Sequence``). 2-D matrix and vision payloads are rejected with guidance:
  TacStack cannot encode MP4 video, so image streams should flatten to taxels
  or use the MCAP embed export for full-fidelity frames.
- data files are written snappy-compressed with dictionary encoding, like the
  LeRobot writer; ``meta/stats.json`` carries min / max / mean / std / count
  per feature (population std, ddof=0).

pyarrow is imported lazily so the rest of the package never needs it
(``uv sync --extra lerobot``).
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from tacstack.core import TactileObservation

CODEBASE_VERSION = "v3.0"
DEFAULT_FEATURE_KEY = "observation.tactile"

_CHUNK_SIZE = 1000
_DATA_PATH_TEMPLATE = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
_VIDEO_PATH_TEMPLATE = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
_PAYLOAD_DTYPES = frozenset({"float32", "float64"})
_ARRAY_DTYPES = frozenset({"float32", "float64", "int32", "int64"})

_SCALAR_SPECS: dict[str, dict[str, Any]] = {
    "timestamp": {"dtype": "float32", "shape": [1], "names": None},
    "frame_index": {"dtype": "int64", "shape": [1], "names": None},
    "episode_index": {"dtype": "int64", "shape": [1], "names": None},
    "index": {"dtype": "int64", "shape": [1], "names": None},
    "task_index": {"dtype": "int64", "shape": [1], "names": None},
}


@dataclass(frozen=True)
class LeRobotExportSummary:
    """What one export produced; cheap to print in CLI output."""

    episodes: int
    frames: int
    path: Path


def require_pyarrow() -> tuple[Any, Any]:
    """Return ``(pyarrow, pyarrow.parquet)`` or raise with install guidance."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise ImportError(
            "LeRobot interop requires the optional 'lerobot' extra (pyarrow): "
            "uv sync --extra lerobot"
        ) from error
    return pa, pq


def load_lerobot_info(root: str | Path) -> dict[str, Any]:
    """Load ``meta/info.json`` of a LeRobot dataset directory."""
    info_file = Path(root) / "meta" / "info.json"
    if not info_file.is_file():
        raise FileNotFoundError(f"not a LeRobot dataset (missing {info_file})")
    info: dict[str, Any] = json.loads(info_file.read_text(encoding="utf-8"))
    return info


def resolve_tactile_feature(features: dict[str, Any], requested: str | None = None) -> str:
    """Pick the tactile array feature from a LeRobot ``features`` dict.

    Candidates are ``observation.*`` float/int columns of dimension 1 or 2
    (video/image features are referenced files, not arrays). An explicit
    ``requested`` key must be a candidate; otherwise a single
    tactile-named candidate wins, then a single candidate overall, else a
    ValueError lists the options.
    """
    candidates = sorted(
        key
        for key, spec in features.items()
        if key.startswith("observation.")
        and isinstance(spec, dict)
        and spec.get("dtype") in _ARRAY_DTYPES
        and isinstance(spec.get("shape"), (list, tuple))
        and len(spec["shape"]) in (1, 2)
    )
    if requested is not None:
        if requested not in candidates:
            raise ValueError(
                f"feature {requested!r} is not an observation float/int array feature; "
                f"available: {candidates}"
            )
        return requested
    tactile = [key for key in candidates if "tactile" in key.lower()]
    for group in (tactile, candidates):
        if len(group) == 1:
            return group[0]
    raise ValueError(
        f"cannot pick a tactile feature automatically; pass feature=<key>; candidates: {candidates}"
    )


class _RunningStats:
    """Element-wise min / max / mean / population-std over stacked frames."""

    def __init__(self) -> None:
        self._minimum: np.ndarray | None = None
        self._maximum: np.ndarray | None = None
        self._sum: np.ndarray | None = None
        self._sum_squares: np.ndarray | None = None
        self.count = 0

    def update(self, frames: np.ndarray) -> None:
        """Accumulate one ``(n_frames, ...)`` stack of frames."""
        flat = np.asarray(frames, dtype=np.float64)
        if flat.size == 0:
            return
        if (
            self._minimum is None
            or self._maximum is None
            or self._sum is None
            or self._sum_squares is None
        ):
            self._minimum = flat.min(axis=0)
            self._maximum = flat.max(axis=0)
            self._sum = flat.sum(axis=0)
            self._sum_squares = (flat * flat).sum(axis=0)
        else:
            self._minimum = np.minimum(self._minimum, flat.min(axis=0))
            self._maximum = np.maximum(self._maximum, flat.max(axis=0))
            self._sum = self._sum + flat.sum(axis=0)
            self._sum_squares = self._sum_squares + (flat * flat).sum(axis=0)
        self.count += flat.shape[0]

    def result(self) -> dict[str, Any]:
        if (
            self._minimum is None
            or self._maximum is None
            or self._sum is None
            or self._sum_squares is None
        ):
            raise RuntimeError("no values accumulated")
        mean = self._sum / self.count
        variance = np.maximum(self._sum_squares / self.count - mean * mean, 0.0)
        return {
            "min": self._minimum.tolist(),
            "max": self._maximum.tolist(),
            "mean": mean.tolist(),
            "std": np.sqrt(variance).tolist(),
            "count": self.count,
        }


class LeRobotDatasetWriter:
    """Writes one LeRobot v3.0 dataset directory, episode by episode.

    ``add_episode`` consumes one replay stream (a TacStack episode) into one
    data parquet file; ``finalize`` writes the metadata files and dataset
    stats. The payload dtype and shape are fixed by the first observation and
    validated against every later frame.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        fps: int,
        feature_key: str = DEFAULT_FEATURE_KEY,
        task: str = "tacstack export",
        robot_type: str | None = None,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self._root = Path(root)
        self._fps = int(fps)
        self._feature_key = feature_key
        self._default_task = task
        self._robot_type = robot_type
        self._tasks: dict[str, int] = {}
        self._episodes: list[dict[str, Any]] = []
        self._total_frames = 0
        self._payload_dtype: str | None = None
        self._payload_shape: tuple[int, ...] | None = None
        self._payload_stats = _RunningStats()
        self._scalar_values: dict[str, list[float]] = {
            name: [] for name in ("timestamp", *_SCALAR_SPECS)
        }

    def add_episode(
        self, observations: Iterable[TactileObservation], *, task: str | None = None
    ) -> int:
        """Consume one episode stream into a data parquet file; return its index."""
        pa, pq = require_pyarrow()
        task_name = self._default_task if task is None else task
        if task_name not in self._tasks:
            self._tasks[task_name] = len(self._tasks)
        task_index = self._tasks[task_name]
        episode_index = len(self._episodes)

        payload_rows: list[list[float]] = []
        for observation in observations:
            payload = self._payload(observation)
            payload_rows.append(payload.tolist())
        if not payload_rows:
            raise ValueError("episode stream is empty")
        length = len(payload_rows)
        frame_indexes = list(range(length))
        global_indexes = list(range(self._total_frames, self._total_frames + length))
        timestamps = [frame_index / self._fps for frame_index in frame_indexes]

        self._payload_stats.update(np.asarray(payload_rows, dtype=np.float64))
        self._scalar_values["timestamp"].extend(timestamps)
        self._scalar_values["frame_index"].extend(float(value) for value in frame_indexes)
        self._scalar_values["episode_index"].extend([float(episode_index)] * length)
        self._scalar_values["index"].extend(float(value) for value in global_indexes)
        self._scalar_values["task_index"].extend([float(task_index)] * length)

        payload_type = pa.list_(pa.float32() if self._payload_dtype == "float32" else pa.float64())
        table = pa.Table.from_pydict(
            {
                "frame_index": pa.array(frame_indexes, type=pa.int64()),
                "timestamp": pa.array(timestamps, type=pa.float32()),
                "episode_index": pa.array([episode_index] * length, type=pa.int64()),
                "index": pa.array(global_indexes, type=pa.int64()),
                "task_index": pa.array([task_index] * length, type=pa.int64()),
                self._feature_key: pa.array(payload_rows, type=payload_type),
            }
        )
        chunk_index = episode_index // _CHUNK_SIZE
        file_index = episode_index % _CHUNK_SIZE
        data_file = self._root / _DATA_PATH_TEMPLATE.format(
            chunk_index=chunk_index, file_index=file_index
        )
        data_file.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, data_file, compression="snappy", use_dictionary=True)

        self._episodes.append(
            {
                "episode_index": episode_index,
                "tasks": [task_name],
                "length": length,
                "chunk_index": chunk_index,
                "file_index": file_index,
                "from_index": global_indexes[0],
                "to_index": global_indexes[-1],
            }
        )
        self._total_frames += length
        return episode_index

    def finalize(self) -> LeRobotExportSummary:
        """Write meta/info.json, tasks, episode metadata and stats."""
        if not self._episodes:
            raise ValueError("no episodes added; call add_episode() first")
        self._write_info()
        self._write_tasks()
        self._write_episodes_meta()
        self._write_stats()
        return LeRobotExportSummary(
            episodes=len(self._episodes), frames=self._total_frames, path=self._root
        )

    def _payload(self, observation: TactileObservation) -> np.ndarray:
        if observation.taxels is None:
            if observation.tactile_image is not None:
                raise ValueError(
                    "LeRobot export stores 1-D taxel features; this stream carries "
                    "tactile_image (vision tactile). Flatten to taxels or use the "
                    "MCAP embed export for image payloads."
                )
            raise ValueError("observation carries no tactile payload (taxels is None)")
        array = np.asarray(observation.taxels)
        dtype = array.dtype.name
        if dtype not in _PAYLOAD_DTYPES:
            raise ValueError(f"taxel dtype must be one of {sorted(_PAYLOAD_DTYPES)}, got {dtype}")
        if array.ndim != 1:
            raise ValueError(f"taxel array must be 1-D for LeRobot export, got shape {array.shape}")
        if self._payload_dtype is None or self._payload_shape is None:
            self._payload_dtype = dtype
            self._payload_shape = tuple(array.shape)
        elif dtype != self._payload_dtype or array.shape != self._payload_shape:
            raise ValueError(
                f"payload mismatch: expected {self._payload_dtype} {self._payload_shape}, "
                f"got {dtype} {array.shape}"
            )
        return array

    def _write_info(self) -> None:
        assert self._payload_dtype is not None and self._payload_shape is not None
        features: dict[str, Any] = {
            self._feature_key: {
                "dtype": self._payload_dtype,
                "shape": list(self._payload_shape),
                "names": None,
            }
        }
        features.update({name: dict(spec) for name, spec in _SCALAR_SPECS.items()})
        info = {
            "codebase_version": CODEBASE_VERSION,
            "fps": self._fps,
            "robot_type": self._robot_type,
            "total_episodes": len(self._episodes),
            "total_frames": self._total_frames,
            "total_tasks": len(self._tasks),
            "chunks_size": _CHUNK_SIZE,
            "data_files_size_in_mb": 100,
            "video_files_size_in_mb": 200,
            "data_path": _DATA_PATH_TEMPLATE,
            "video_path": _VIDEO_PATH_TEMPLATE,
            "features": features,
        }
        self._root.mkdir(parents=True, exist_ok=True)
        info_file = self._root / "meta" / "info.json"
        info_file.parent.mkdir(parents=True, exist_ok=True)
        info_file.write_text(json.dumps(info, indent=2, allow_nan=False), encoding="utf-8")

    def _write_tasks(self) -> None:
        pa, pq = require_pyarrow()
        ordered = sorted(self._tasks.items(), key=lambda item: item[1])
        table = pa.Table.from_pydict(
            {
                "task_index": pa.array([index for _, index in ordered], type=pa.int64()),
                "task": pa.array([name for name, _ in ordered], type=pa.string()),
            }
        )
        tasks_file = self._root / "meta" / "tasks.parquet"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, tasks_file, compression="snappy", use_dictionary=True)

    def _write_episodes_meta(self) -> None:
        pa, pq = require_pyarrow()
        indexes = [episode["episode_index"] for episode in self._episodes]
        table = pa.Table.from_pydict(
            {
                "episode_index": pa.array(indexes, type=pa.int64()),
                "tasks": pa.array(
                    [episode["tasks"] for episode in self._episodes],
                    type=pa.list_(pa.string()),
                ),
                "length": pa.array(
                    [episode["length"] for episode in self._episodes], type=pa.int64()
                ),
                "meta/episodes/chunk_index": pa.array([0] * len(self._episodes), type=pa.int64()),
                "meta/episodes/file_index": pa.array([0] * len(self._episodes), type=pa.int64()),
                "data/chunk_index": pa.array(
                    [episode["chunk_index"] for episode in self._episodes], type=pa.int64()
                ),
                "data/file_index": pa.array(
                    [episode["file_index"] for episode in self._episodes], type=pa.int64()
                ),
                "dataset_from_index": pa.array(
                    [episode["from_index"] for episode in self._episodes], type=pa.int64()
                ),
                "dataset_to_index": pa.array(
                    [episode["to_index"] for episode in self._episodes], type=pa.int64()
                ),
            }
        )
        episodes_file = self._root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
        episodes_file.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, episodes_file, compression="snappy", use_dictionary=True)

    def _write_stats(self) -> None:
        stats: dict[str, Any] = {
            self._feature_key: self._payload_stats.result(),
            **{name: self._scalar_result(values) for name, values in self._scalar_values.items()},
        }
        stats_file = self._root / "meta" / "stats.json"
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        stats_file.write_text(json.dumps(stats, indent=2, allow_nan=False), encoding="utf-8")

    def _scalar_result(self, values: list[float]) -> dict[str, Any]:
        array = np.asarray(values, dtype=np.float64)
        return {
            "min": [float(array.min())],
            "max": [float(array.max())],
            "mean": [float(array.mean())],
            "std": [float(array.std())],
            "count": int(array.size),
        }
