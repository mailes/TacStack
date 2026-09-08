"""Blocking replay adapter over LeRobot v3.0 dataset directories.

Reads the tactile feature (a 1-D or 2-D float/int array column declared in
``meta/info.json``) from a local LeRobot dataset and replays it as
TactileObservations per the blocking adapter contract: ``read()`` returns one
observation per call and raises ``EOFError`` when the dataset is exhausted.

Only the tabular modality is supported: video features are referenced MP4
files that TacStack cannot decode without heavyweight dependencies. Declared
taxel streams (``observation.tactile`` or any ``observation.*`` float/int
array feature) replay into the same runtime / model / event pipeline as the
other adapters.

Timestamps: LeRobot defines ``timestamp = frame_index / fps``; the adapter
stamps ``timestamp_ns`` from the frame index (``frame_index * 1e9 / fps``,
the same index-domain rule as the OXT adapter) and preserves the file's
timestamp column in ``metadata["timestamp"]``.

Feature selection: ``feature=<key>`` picks the column; otherwise the single
tactile-named candidate wins, then a single ``observation.*`` array feature
overall; ambiguity raises with the candidate list.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from tacstack.core import SensorDescriptor, TactileObservation
from tacstack.integrations.lerobot import (
    CODEBASE_VERSION,
    load_lerobot_info,
    require_pyarrow,
    resolve_tactile_feature,
)

_ROW_COLUMNS = ("frame_index", "timestamp", "episode_index", "index", "task_index")
_BATCH_SIZE = 256


class LeRobotAdapter:
    """Replay one tactile feature from a LeRobot v3.0 dataset directory."""

    def __init__(
        self,
        path: str | Path,
        *,
        feature: str | None = None,
        episode: int | None = None,
    ) -> None:
        self._root = Path(path)
        if not self._root.is_dir():
            raise FileNotFoundError(f"LeRobot dataset not found: {self._root}")
        self._feature_request = feature
        self._episode = episode
        self._descriptor: SensorDescriptor | None = None
        self._rows: Iterator[dict[str, Any]] | None = None
        self._feature_key: str | None = None
        self._shape: tuple[int, ...] | None = None
        self._dtype_name: str | None = None
        self._fps = 0
        self._tasks: dict[int, str] = {}

    def descriptor(self) -> SensorDescriptor:
        """Sensor identity of the replayed stream; available after open()."""
        if self._descriptor is None:
            raise RuntimeError("descriptor() requires open(); call open() first")
        return self._descriptor

    def open(self) -> None:
        """Validate the dataset layout and prepare the row stream."""
        if self._rows is not None:
            return
        _, pq = require_pyarrow()
        info = load_lerobot_info(self._root)
        version = str(info.get("codebase_version", ""))
        if not version.startswith("v3."):
            raise ValueError(
                f"unsupported LeRobot dataset version {version!r}; TacStack reads "
                f"{CODEBASE_VERSION} layouts (v2.1 datasets: python -m "
                "lerobot.scripts.convert_dataset_v21_to_v30)"
            )
        features = info.get("features", {})
        if not isinstance(features, dict):
            raise ValueError("info.json 'features' must be a dict")
        feature_key = resolve_tactile_feature(features, self._feature_request)
        spec = features[feature_key]
        shape = tuple(int(size) for size in spec["shape"])
        fps = int(info["fps"])
        if fps <= 0:
            raise ValueError(f"info.json fps must be positive, got {fps}")
        self._feature_key = feature_key
        self._shape = shape
        self._dtype_name = str(spec["dtype"])
        self._fps = fps
        self._tasks = self._read_tasks(pq)
        self._descriptor = SensorDescriptor(
            sensor_id=f"lerobot:{self._root.name}:{feature_key}",
            vendor="LeRobot",
            model=str(info.get("robot_type") or "lerobot-dataset"),
            modality="taxel",
            frame_id=feature_key,
            sample_rate_hz=float(fps),
            capabilities=frozenset({"taxel_force"}),
        )
        self._rows = self._iter_rows(pq)

    def read(self) -> TactileObservation:
        """Return the next observation of the selected feature; EOFError at end."""
        if self._descriptor is None or self._rows is None or self._feature_key is None:
            raise RuntimeError("read() requires open(); call open() first")
        row = next(self._rows, None)
        if row is None:
            raise EOFError(f"LeRobot dataset {self._root} exhausted")
        payload = np.asarray(row[self._feature_key], dtype=np.dtype(self._dtype_name))
        if payload.shape != self._shape:
            raise ValueError(
                f"feature {self._feature_key!r} frame shape {payload.shape} does not "
                f"match the declared shape {self._shape}"
            )
        frame_index = int(row["frame_index"])
        metadata: dict[str, Any] = {
            "frame_index": frame_index,
            "episode_index": int(row["episode_index"]),
            "index": int(row["index"]),
            "task_index": int(row["task_index"]),
            "task": self._tasks.get(int(row["task_index"])),
            "timestamp": float(row["timestamp"]),
        }
        return TactileObservation(
            timestamp_ns=int(round(frame_index * 1_000_000_000 / self._fps)),
            sensor=self._descriptor,
            raw=payload,
            taxels=payload,
            metadata=metadata,
        )

    def close(self) -> None:
        # the descriptor stays valid: it only depends on dataset metadata, so
        # callers may query it after closing
        self._rows = None

    def _read_tasks(self, pq: Any) -> dict[int, str]:
        tasks_file = self._root / "meta" / "tasks.parquet"
        if not tasks_file.is_file():
            return {}
        table = pq.read_table(tasks_file)
        if "task" not in table.column_names or "task_index" not in table.column_names:
            return {}
        pairs = zip(
            table.column("task_index").to_pylist(),
            table.column("task").to_pylist(),
            strict=True,
        )
        return {int(index): str(task) for index, task in pairs}

    def _data_files(self) -> list[Path]:
        files = sorted(self._root.glob("data/**/*.parquet"))
        if not files:
            raise ValueError(f"no data parquet files under {self._root / 'data'}")
        return files

    def _iter_rows(self, pq: Any) -> Iterator[dict[str, Any]]:
        columns = [self._feature_key, *_ROW_COLUMNS]
        for data_file in self._data_files():
            parquet = pq.ParquetFile(data_file)
            for batch in parquet.iter_batches(batch_size=_BATCH_SIZE, columns=columns):
                for row in batch.to_pylist():
                    if self._episode is not None and row["episode_index"] != self._episode:
                        continue
                    yield row
