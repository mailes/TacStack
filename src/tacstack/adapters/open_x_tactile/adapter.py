"""Open-X-Tactile (FTP-1) adapter: tar-wrapped zarr episodes to TactileObservation.

Contract and boundary:
- The source is an uncompressed tar wrapping ``<task>.zarr`` stores in the
  FTP-1 release layout, or an extracted directory of the same layout. Streaming
  HTTP sources are out of scope; the tar must be a seekable local file.
- One adapter instance replays one (task, episode, tactile stream). ``read()``
  returns one observation per frame and raises ``EOFError`` at the end of the
  episode; other errors propagate.
- FTP-1 timestamps are frame indices without a wall-clock origin (the official
  FTP-1 parser synthesizes ``arange``). With ``timestamp_domain="frame_index"``
  (default) ``timestamp_ns`` is derived: ``round(index * 1e9 / rate_hz)`` when
  ``rate_hz`` is set, otherwise the index stays in a documented index domain
  (``index * 1e9``). With ``timestamp_domain="nanoseconds"`` the stored value is
  used as-is for releases that ship real timestamps. The original index is
  always preserved in ``metadata["oxt_frame_index"]``.
- Raw-first: per-frame small arrays (joints, instructions, area indices) are
  preserved in ``raw``; tactile payloads go to ``tactile_image`` / ``taxels``
  according to the stream's declared type; bulk non-tactile streams (cameras)
  stay in the source archive and are only referenced by name in ``metadata``.
"""

from math import isfinite
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from tacstack.adapters.open_x_tactile.archive import (
    OpenXTactileArchive,
    OpenXTactileTask,
    TactileStreamInfo,
)
from tacstack.core import SensorDescriptor, TactileObservation

TimestampDomain = Literal["frame_index", "nanoseconds"]

# Bulk auxiliary streams that stay in the source archive instead of being
# copied into every observation (referenced by name in metadata only).
_BULK_STREAM_TOKENS = ("camera",)


class OpenXTactileAdapter:
    """Replay one tactile stream of one FTP-1 episode as TactileObservations."""

    def __init__(
        self,
        source: str | Path,
        *,
        task: str,
        episode: int = 0,
        stream: str | None = None,
        rate_hz: float | None = None,
        timestamp_domain: TimestampDomain = "frame_index",
    ) -> None:
        if rate_hz is not None and (not isfinite(rate_hz) or rate_hz <= 0):
            raise ValueError("rate_hz must be finite and positive when given")
        self._source = source
        self._task_name = task
        self._episode = episode
        self._stream_name = stream
        self._rate_hz = rate_hz
        self._timestamp_domain: TimestampDomain = timestamp_domain
        self._archive: OpenXTactileArchive | None = None
        self._task: OpenXTactileTask | None = None
        self._stream: TactileStreamInfo | None = None
        self._descriptor: SensorDescriptor | None = None
        self._start = 0
        self._end = 0
        self._cursor = 0
        self._extra_streams: tuple[str, ...] = ()

    def descriptor(self) -> SensorDescriptor:
        """Sensor identity of the replayed stream; available after open()."""
        if self._descriptor is None:
            raise RuntimeError("descriptor() requires open(); call open() first")
        return self._descriptor

    def open(self) -> None:
        """Open the archive, resolve the episode and stream, build the descriptor."""
        if self._task is not None:
            return
        archive = OpenXTactileArchive(self._source)
        task = archive.open_task(self._task_name)
        stream = self._resolve_stream(task)
        start, end = task.episode_bounds(self._episode)
        if end == start:
            raise ValueError(
                f"task {self._task_name!r}: episode {self._episode} is empty "
                f"(use the dataset list command to inspect available episodes)"
            )
        self._archive = archive
        self._task = task
        self._stream = stream
        self._start = start
        self._end = end
        self._cursor = start
        self._descriptor = self._build_descriptor(stream)

    def _resolve_stream(self, task: OpenXTactileTask) -> TactileStreamInfo:
        streams = task.streams()
        if not streams:
            raise ValueError(f"task {self._task_name!r}: no tactile data streams found")
        if self._stream_name is None:
            if len(streams) > 1:
                names = ", ".join(stream.stream for stream in streams)
                raise ValueError(
                    f"task {self._task_name!r} has multiple streams; pick one: {names}"
                )
            return streams[0]
        for stream in streams:
            if stream.stream == self._stream_name:
                return stream
        names = ", ".join(stream.stream for stream in streams)
        raise KeyError(
            f"stream {self._stream_name!r} not found in task {self._task_name!r}; "
            f"available: {names}"
        )

    def _build_descriptor(self, stream: TactileStreamInfo) -> SensorDescriptor:
        # "matrix" is a 2D taxel grid (verified in RH20TCfg7Tactile); it and the
        # other non-image kinds all replay through the taxels payload
        modality = {
            "image": "vision_tactile",
            "state": "taxel",
            "binary": "taxel",
            "matrix": "taxel",
        }.get(stream.kind, stream.kind)
        capabilities = {"tactile_image"} if stream.kind == "image" else {"taxel_force"}
        return SensorDescriptor(
            sensor_id=f"oxt:{self._task_name}:{stream.stream}",
            vendor="Open-X-Tactile",
            model=stream.sensor,
            modality=modality,
            frame_id=stream.stream,
            sample_rate_hz=self._rate_hz,
            capabilities=frozenset(capabilities),
        )

    def read(self) -> TactileObservation:
        """Return the next frame; raise EOFError at the end of the episode."""
        if self._task is None or self._stream is None or self._descriptor is None:
            raise RuntimeError("read() requires open(); call open() first")
        if self._cursor >= self._end:
            raise EOFError(f"episode {self._episode} of task {self._task_name!r} exhausted")
        index = self._cursor
        self._cursor += 1
        observation = TactileObservation(
            timestamp_ns=self._timestamp_ns(index),
            sensor=self._descriptor,
            raw=self._raw_payload(index),
            calibration_id=None,
            quality={},
            metadata=self._metadata(index),
        )
        payload = self._tactile_payload(index)
        if self._stream.kind == "image":
            observation.tactile_image = payload
        else:
            observation.taxels = payload
        return observation

    def close(self) -> None:
        # the descriptor stays valid: it only depends on configuration and
        # archive metadata, so callers may query it after closing
        if self._archive is not None:
            self._archive.close()
        self._archive = None
        self._task = None
        self._stream = None

    def _timestamp_ns(self, index: int) -> int:
        assert self._task is not None
        if "timestamps" in self._task.array_names:
            value = np.asarray(self._task.array("data/timestamps")[index]).item()
            raw = int(value)
        else:
            raw = index
        if self._timestamp_domain == "nanoseconds":
            return raw
        if self._rate_hz is not None:
            return round(raw * 1_000_000_000 / self._rate_hz)
        return raw * 1_000_000_000

    def _tactile_payload(self, index: int) -> npt.NDArray[Any]:
        assert self._task is not None and self._stream is not None
        data = self._task.array(f"data/{self._stream.data_key}")
        frame = np.asarray(data[index])
        if frame.shape[0] != self._stream.areas:
            raise ValueError(
                f"task {self._task_name!r}: stream {self._stream.stream!r} area axis mismatch "
                f"at frame {index}: expected {self._stream.areas}, got {frame.shape[0]}"
            )
        return frame

    def _raw_payload(self, index: int) -> dict[str, Any]:
        assert self._task is not None and self._stream is not None
        payload: dict[str, Any] = {}
        for name in self._task.array_names:
            if name == self._stream.data_key or name == "timestamps":
                continue
            if "_tactile_" in name:
                # every tactile stream belongs to its own adapter instance
                continue
            if any(token in name for token in _BULK_STREAM_TOKENS):
                continue
            value = np.asarray(self._task.array(f"data/{name}")[index])
            payload[name] = value.item() if value.ndim == 0 else value.copy()
        return payload

    def _metadata(self, index: int) -> dict[str, Any]:
        assert self._task is not None and self._stream is not None
        metadata: dict[str, Any] = {
            "oxt_task": self._task_name,
            "oxt_episode": self._episode,
            "oxt_frame_index": index,
            "oxt_stream": self._stream.stream,
            "oxt_tactile_sensor": self._stream.sensor,
            "oxt_tactile_type": self._stream.kind,
            "oxt_timestamp_domain": self._timestamp_domain,
            "oxt_camera_streams": tuple(
                name
                for name in self._task.array_names
                if any(token in name for token in _BULK_STREAM_TOKENS)
            ),
        }
        area_key = self._stream.data_key.replace("_data_", "_area_", 1)
        if area_key in self._task.array_names:
            areas = np.asarray(self._task.array(f"data/{area_key}")[index])
            metadata["oxt_tactile_areas"] = tuple(int(v) for v in areas.tolist())
        return metadata
