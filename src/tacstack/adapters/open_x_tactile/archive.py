"""Task inventory and zarr array access for Open-X-Tactile (FTP-1) archives.

Contract:
- A source is either an uncompressed tar wrapping one or more ``<task>.zarr``
  stores (the OXT/FTP-1 release layout) or an extracted directory containing
  those ``<task>.zarr`` directories.
- Each task is a zarr v2 group with ``meta/episode_ends`` (int64, cumulative
  last-frame index per episode) and a ``data`` group of time-major arrays
  (leading axis T = total frames).
- Tactile streams follow the FTP-1 key convention ``<side>_tactile_data_<group>``
  with ``<side>_tactile_{sensor,type,area}_<group>`` siblings.
- Array discovery uses store-level listing, not group traversal: ``data`` is an
  implicit group in real releases (a directory with only ``.zattrs``), which
  zarr group listing does not report.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import zarr
from zarr.abc.store import Store
from zarr.storage import LocalStore

from tacstack.adapters.open_x_tactile.store import TarStore

_TACTILE_DATA_RE = re.compile(r"^(?P<side>[a-z0-9]+)_tactile_data_(?P<group>[a-z0-9_]+)$")
_ZARR_SUFFIX = ".zarr"


@dataclass(frozen=True)
class TactileStreamInfo:
    """One tactile data stream discovered inside a task's ``data`` group."""

    stream: str  # "<side>_<group>", e.g. "right_gripper"
    data_key: str  # zarr array name, e.g. "right_tactile_data_gripper"
    sensor: str  # declared sensor model, e.g. "GelSightMini"
    kind: str  # declared payload type: "image" | "state" | "binary"
    areas: int  # size of the tactile-area axis


@dataclass(frozen=True)
class TaskInfo:
    """Episode/shape summary of one task; safe to print or export."""

    name: str
    episodes: int
    frames: int
    arrays: tuple[str, ...]
    streams: tuple[TactileStreamInfo, ...]


class OpenXTactileTask:
    """Opened zarr store of one task; caches arrays and resolves episodes."""

    def __init__(self, name: str, store: Store) -> None:
        self.name = name
        self._store = store
        self._arrays: dict[str, zarr.Array[Any]] = {}
        self.array_names: tuple[str, ...] = tuple(self._list_array_names())

    def _list_array_names(self) -> list[str]:
        async def collect() -> list[str]:
            names = []
            async for key in self._store.list_prefix("data/"):
                if key.endswith("/.zarray"):
                    names.append(key.removeprefix("data/").removesuffix("/.zarray"))
            return names

        return sorted(asyncio.run(collect()))

    def array(self, name: str) -> zarr.Array[Any]:
        """Open (and cache) one data or meta array by its store-relative path."""
        cached = self._arrays.get(name)
        if cached is not None:
            return cached
        opened = zarr.open_array(store=self._store, path=name, zarr_format=2, mode="r")
        self._arrays[name] = opened
        return opened

    def episode_ends(self) -> npt.NDArray[np.int64]:
        ends = np.asarray(self.array("meta/episode_ends")[:])
        if ends.ndim != 1 or ends.size == 0:
            raise ValueError(f"task {self.name!r}: meta/episode_ends must be a non-empty 1-D array")
        return ends

    def episode_bounds(self, episode: int) -> tuple[int, int]:
        """Return [start, end) frame indices; raise IndexError for unknown episodes."""
        ends = self.episode_ends()
        if not 0 <= episode < ends.size:
            raise IndexError(
                f"task {self.name!r}: episode {episode} out of range (0..{ends.size - 1})"
            )
        start = int(ends[episode - 1]) if episode > 0 else 0
        end = int(ends[episode])
        if end < start:
            raise ValueError(f"task {self.name!r}: episode {episode} has negative length")
        return start, end

    def streams(self) -> tuple[TactileStreamInfo, ...]:
        """Discover tactile streams under the FTP-1 key convention."""
        streams: list[TactileStreamInfo] = []
        for name in self.array_names:
            match = _TACTILE_DATA_RE.match(name)
            if match is None:
                continue
            side, group = match["side"], match["group"]
            prefix = f"{side}_tactile"
            sensor = self._first_string(f"{prefix}_sensor_{group}", default="unknown")
            kind = self._first_string(f"{prefix}_type_{group}", default="unknown")
            data_shape = self.array(f"data/{name}").shape
            if len(data_shape) < 2:
                raise ValueError(
                    f"task {self.name!r}: tactile array {name!r} must have an area axis"
                )
            streams.append(
                TactileStreamInfo(
                    stream=f"{side}_{group}",
                    data_key=name,
                    sensor=sensor,
                    kind=kind,
                    areas=int(data_shape[1]),
                )
            )
        return tuple(streams)

    def _first_string(self, name: str, default: str) -> str:
        if name not in self.array_names:
            return default
        value = self.array(f"data/{name}")[0]
        text = str(np.asarray(value).item())
        return text or default

    def info(self) -> TaskInfo:
        return TaskInfo(
            name=self.name,
            episodes=int(self.episode_ends().size),
            frames=int(self.episode_ends()[-1]),
            arrays=self.array_names,
            streams=self.streams(),
        )


class OpenXTactileArchive:
    """Inventory of tasks inside an OXT tar or extracted directory source."""

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)
        if not self.source.exists():
            raise FileNotFoundError(f"source not found: {self.source}")
        self._task_roots = self._discover_task_roots()
        self._tasks: dict[str, OpenXTactileTask] = {}

    def _discover_task_roots(self) -> dict[str, str]:
        """Map task name -> store root (tar member prefix with trailing slash)."""
        if self.source.is_dir():
            roots: dict[str, str] = {}
            for child in sorted(self.source.iterdir()):
                if child.is_dir() and child.name.endswith(_ZARR_SUFFIX):
                    roots[child.name.removesuffix(_ZARR_SUFFIX)] = child.name
            return roots
        store = TarStore(self.source)
        try:

            async def collect() -> dict[str, str]:
                found: dict[str, str] = {}
                async for key in store.list():
                    if ".zarr/" not in key:
                        continue
                    before, after = key.split(".zarr/", 1)
                    task_name = before.rsplit("/", 1)[-1] if "/" in before else before
                    if after:
                        found.setdefault(task_name, f"{before}.zarr/")
                return found

            return asyncio.run(collect())
        finally:
            store.close()

    def task_names(self) -> list[str]:
        return sorted(self._task_roots)

    def open_task(self, task: str) -> OpenXTactileTask:
        """Open one task by name; closed together with this archive."""
        cached = self._tasks.get(task)
        if cached is not None:
            return cached
        root = self._task_roots.get(task)
        if root is None:
            available = ", ".join(self.task_names()) or "none"
            raise KeyError(
                f"task {task!r} not found in {self.source.name}; available tasks: {available}"
            )
        if self.source.is_dir():
            store: Store = LocalStore(self.source / root, read_only=True)
        else:
            store = TarStore(self.source, root=root)
        opened = OpenXTactileTask(task, store)
        self._tasks[task] = opened
        return opened

    def close(self) -> None:
        for task in self._tasks.values():
            if isinstance(task._store, TarStore):
                task._store.close()
        self._tasks.clear()

    def __enter__(self) -> "OpenXTactileArchive":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
