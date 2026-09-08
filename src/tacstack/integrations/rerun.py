"""Rerun replay of TactileObservation streams on synchronized timelines.

Contract:
- One RerunReplay instance is one Rerun recording; it can serve any number of
  observation streams (from different adapters) into the same timelines.
- Two timelines per observation: ``timestamp`` (nanoseconds on a duration
  timeline; for FTP-1 index-domain data this is pseudo-time that only
  guarantees monotonic ordering) and ``frame_index`` (sequence, from
  ``metadata["oxt_frame_index"]`` when present).
- Visual mapping, driven purely by what the observation carries:
  ``tactile_image`` areas log as images; ``taxels`` with a 2-D taxel grid log
  as an exact tensor plus a per-area [0, 1] heatmap (magnitude over the last
  axis); vector-like ``taxels`` log as scalar series (6-wide streams get
  ``fx..tz`` display labels for 6-axis F/T-style streams; raw semantics are
  untouched); ``raw`` scalars and small arrays log as scalar series, HxWxC
  arrays (opted-in cameras) log as images, anything else logs as a tensor.
- String values log as text on change only, so per-frame instructions do not
  spam the recording.
- On ``flush()`` a self-describing blueprint is sent, laying out exactly the
  entities this recording logged; without it the viewer may reuse a cached
  auto-layout from an earlier recording under the same application id.
- Requires the optional ``rerun`` extra (``uv sync --extra rerun``); this
  module must only be imported where that failure is handled.
"""

from pathlib import Path

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

from tacstack.annotations import TactileMark
from tacstack.core import SensorDescriptor, TactileEvent, TactileObservation
from tacstack.core.serialization import to_debug_json

# Display labels for 6-wide streams such as ATIAxia80M20 force/torque. These
# are visualization labels only; payload semantics stay in the observation.
_FT_COMPONENT_NAMES = ("fx", "fy", "fz", "tx", "ty", "tz")
_MAX_SCALAR_SERIES = 32


def _entity_safe(name: str) -> str:
    """Map a sensor_id like ``oxt:task:stream`` to a valid entity path."""
    return name.replace(":", "/")


def _view_name(path: str) -> str:
    """Short tab label: the last two path segments ("tactile_image/area_0")."""
    parts = path.split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else path


class RerunReplay:
    """Log TactileObservations to a Rerun recording for synchronized replay."""

    def __init__(self, *, application_id: str = "tacstack") -> None:
        self._stream = rr.RecordingStream(application_id)
        self._descriptors_logged: set[str] = set()
        self._last_text: dict[str, str] = {}
        # ordered entity bookkeeping for the self-describing blueprint
        self._image_entities: dict[str, None] = {}
        self._tensor_entities: dict[str, None] = {}
        self._text_entities: dict[str, None] = {}
        self._scalar_groups: dict[str, None] = {}

    def save(self, path: str | Path) -> None:
        """Write the recording to a .rrd file as it is logged."""
        self._stream.save(path)

    def spawn(self, *, port: int = 9876) -> None:
        """Start a local Rerun viewer and stream to it."""
        self._stream.spawn(port=port)

    def connect(self, url: str | None = None) -> None:
        """Stream to an already-running viewer (grpc url)."""
        self._stream.connect_grpc(url)

    def flush(self) -> None:
        self._send_blueprint()
        self._stream.flush()

    def log_observation(self, observation: TactileObservation) -> None:
        """Log one observation on the timelines; root entity = sensor_id."""
        root = _entity_safe(observation.sensor.sensor_id)
        self._log_time(observation)
        self._log_descriptor(root, observation.sensor)
        self._log_tactile(root, observation)
        self._log_raw(root, observation)

    def log_annotation(self, mark: TactileMark) -> None:
        """Place one annotation mark on the timelines (entity ``annotations/<mark>``)."""
        path = f"annotations/{mark.mark}"
        self._stream.set_time("timestamp", duration=np.timedelta64(mark.timestamp_ns, "ns"))
        self._stream.set_time("frame_index", sequence=mark.oxt_frame_index)
        self._text_entities.setdefault(path, None)
        self._stream.log(path, rr.TextDocument(f"{mark.mark} {mark.label} ({mark.user})"))

    def log_event(self, event: TactileEvent) -> None:
        """Place one TactileEvent on the timelines as a scalar marker.

        The probability lands on ``<sensor>/events/<kind>`` so the Series row
        of the blueprint renders one curve per event kind.
        """
        path = f"{_entity_safe(event.sensor_id)}/events/{event.kind}"
        self._stream.set_time("timestamp", duration=np.timedelta64(event.timestamp_ns, "ns"))
        frame = event.metadata.get("oxt_frame_index")
        if frame is not None:
            self._stream.set_time("frame_index", sequence=int(frame))
        self._scalar_groups.setdefault(path, None)
        self._stream.log(path, rr.Scalars([float(event.probability)]))

    def _log_time(self, observation: TactileObservation) -> None:
        # np.timedelta64("ns") carries exact nanoseconds; a plain int would be
        # interpreted as seconds by rerun and overflow int64 past ~9.2e9 ns
        duration = np.timedelta64(int(observation.timestamp_ns), "ns")
        self._stream.set_time("timestamp", duration=duration)
        frame = observation.metadata.get("oxt_frame_index")
        if frame is not None:
            self._stream.set_time("frame_index", sequence=int(frame))

    def _log_descriptor(self, root: str, sensor: SensorDescriptor) -> None:
        if sensor.sensor_id in self._descriptors_logged:
            return
        self._stream.log(
            root,
            rr.TextDocument(to_debug_json(sensor), media_type="application/json"),
            static=True,
        )
        self._descriptors_logged.add(sensor.sensor_id)

    def _area_ids(self, observation: TactileObservation, count: int) -> tuple[int, ...]:
        declared = observation.metadata.get("oxt_tactile_areas")
        if declared is not None:
            ids = tuple(int(v) for v in declared)
            if len(ids) >= count:
                return ids[:count]
        return tuple(range(count))

    def _log_tactile(self, root: str, observation: TactileObservation) -> None:
        if observation.tactile_image is not None:
            frames = np.asarray(observation.tactile_image)
            areas = self._area_ids(observation, frames.shape[0])
            for i, area in enumerate(areas):
                path = f"{root}/tactile_image"
                if len(areas) > 1:
                    path += f"/area_{area}"
                self._image_entities.setdefault(path, None)
                self._stream.log(path, rr.Image(frames[i]))
        if observation.taxels is not None:
            payload = np.asarray(observation.taxels)
            areas = self._area_ids(observation, payload.shape[0])
            self._log_taxels(root, payload, areas)

    def _log_taxels(self, root: str, payload: np.ndarray, areas: tuple[int, ...]) -> None:
        tensor_path = f"{root}/taxels"
        self._tensor_entities.setdefault(tensor_path, None)
        self._stream.log(tensor_path, rr.Tensor(payload))
        if payload.ndim >= 3:
            # (areas, *grid[, axes]): magnitude over the trailing axis as heatmap
            magnitude = np.linalg.norm(payload, axis=-1) if payload.ndim >= 4 else np.abs(payload)
            for i, area in enumerate(areas):
                frame = magnitude[i].astype(np.float32)
                peak = float(frame.max()) if frame.size else 0.0
                if peak > 0.0:
                    frame = frame / peak
                path = f"{root}/taxel_heatmap"
                if len(areas) > 1:
                    path += f"/area_{area}"
                self._image_entities.setdefault(path, None)
                self._stream.log(path, rr.Image(frame))
            return
        values = (
            payload.reshape(payload.shape[0], -1) if payload.ndim == 2 else payload.reshape(-1, 1)
        )
        for i, area in enumerate(areas):
            series = values[i]
            names = (
                _FT_COMPONENT_NAMES
                if series.size == len(_FT_COMPONENT_NAMES)
                else tuple(f"c{j}" for j in range(series.size))
            )
            base = f"{root}/taxels"
            if len(areas) > 1:
                base += f"/area_{area}"
            self._scalar_groups.setdefault(base, None)
            for name, value in zip(names, series.tolist(), strict=True):
                self._stream.log(f"{base}/{name}", rr.Scalars([float(value)]))

    def _log_raw(self, root: str, observation: TactileObservation) -> None:
        for name, value in observation.raw.items():
            path = f"{root}/raw/{name}"
            if isinstance(value, (str, np.str_)):
                text = str(value)
                if self._last_text.get(name) != text:
                    self._text_entities.setdefault(path, None)
                    self._stream.log(path, rr.TextDocument(text))
                    self._last_text[name] = text
                continue
            array = np.asarray(value)
            if array.dtype.kind not in "fiub":
                self._text_entities.setdefault(path, None)
                self._stream.log(path, rr.TextDocument(str(value)))
                continue
            if array.ndim == 0:
                self._scalar_groups.setdefault(path, None)
                self._stream.log(path, rr.Scalars([float(array)]))
            elif array.ndim == 3 and array.shape[-1] in (1, 3, 4):
                self._image_entities.setdefault(path, None)
                self._stream.log(path, rr.Image(array))
            elif array.size <= _MAX_SCALAR_SERIES:
                self._scalar_groups.setdefault(path, None)
                for j, item in enumerate(array.reshape(-1).tolist()):
                    self._stream.log(f"{path}/c{j}", rr.Scalars([float(item)]))
            else:
                self._tensor_entities.setdefault(path, None)
                self._stream.log(path, rr.Tensor(array))

    def _send_blueprint(self) -> None:
        """Send a layout covering exactly the entities this recording logged.

        Without this the viewer may reuse a cached auto-layout from an earlier
        recording with the same application id, leaving tabs pointed at
        entities that do not exist in this recording.
        """
        if not (
            self._image_entities
            or self._tensor_entities
            or self._text_entities
            or self._scalar_groups
        ):
            return
        image_tabs = [
            rrb.Spatial2DView(origin=path, name=_view_name(path)) for path in self._image_entities
        ]
        plot_tabs = [
            rrb.TimeSeriesView(origin=path, name=_view_name(path)) for path in self._scalar_groups
        ]
        data_tabs = [
            rrb.TensorView(origin=path, name=_view_name(path)) for path in self._tensor_entities
        ] + [
            rrb.TextDocumentView(origin=path, name=_view_name(path)) for path in self._text_entities
        ]
        rows: list[rrb.Container | rrb.View] = []
        shares: list[float] = []
        if image_tabs:
            rows.append(rrb.Tabs(*image_tabs, name="Images"))
            shares.append(3.0)
        if plot_tabs:
            rows.append(rrb.Tabs(*plot_tabs, name="Series"))
            shares.append(2.0)
        if data_tabs:
            rows.append(rrb.Tabs(*data_tabs, name="Tensors & Text"))
            shares.append(2.0)
        self._stream.send_blueprint(
            rrb.Blueprint(rrb.Vertical(*rows, row_shares=shares), collapse_panels=False)
        )
