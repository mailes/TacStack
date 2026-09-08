"""Blocking replay adapter over TacStack-written MCAP recordings.

Reads the ``tacstack/observations`` JSON channel (schema
``tacstack.tactile_observation.v1``, written by ``tacstack.integrations.mcap``)
and replays one sensor stream as TactileObservations per the blocking adapter
contract: ``read()`` returns one observation per call and raises ``EOFError``
when the recording is exhausted.

Full-fidelity payloads require the recording to be exported with
``embed_payloads=True`` (``tacstack dataset convert --embed``): the embedded
arrays decode back into ``taxels`` / ``tactile_image``. Recordings written in
the default compact mode replay with both payloads set to None and the
summaries preserved in ``metadata["replay_summaries"]`` — the compact export
intentionally does not embed arrays (raw-first: full precision lives in the
source archive).

A recording may hold several sensor streams; replay selects one with
``stream=<sensor_id>``. Unspecified, the first stream in the file wins and
messages from other streams are skipped — this is documented convenience, not
ambiguity resolution.
"""

import base64
import json
from pathlib import Path
from typing import Any

import numpy as np
from mcap.reader import make_reader

from tacstack.core import SensorDescriptor, TactileObservation

TOPIC = "tacstack/observations"


def _decode_array(payload: dict[str, Any] | None) -> np.ndarray | None:
    """Decode an embedded array dict (dtype/shape/data_b64) back to ndarray."""
    if payload is None or "data_b64" not in payload:
        return None
    data = base64.b64decode(payload["data_b64"])
    array = np.frombuffer(data, dtype=np.dtype(payload["dtype"]))
    return array.reshape(payload["shape"]).copy()


class McapReplayAdapter:
    """Replay one sensor stream from a TacStack MCAP recording."""

    def __init__(self, path: str | Path, *, stream: str | None = None) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"recording not found: {self._path}")
        self._stream = stream
        self._file: Any = None
        self._messages: Any = None
        self._descriptor: SensorDescriptor | None = None
        self._resolved_stream: str | None = None

    def descriptor(self) -> SensorDescriptor:
        """Sensor identity of the replayed stream; available after open()."""
        if self._descriptor is None:
            raise RuntimeError("descriptor() requires open(); call open() first")
        return self._descriptor

    def open(self) -> None:
        """Open the recording and resolve the stream from its first message."""
        if self._file is not None:
            return
        self._file = self._path.open("rb")
        reader = make_reader(self._file)
        self._messages = reader.iter_messages(topics=[TOPIC])
        self._pending: dict[str, Any] | None = None
        while self._descriptor is None:
            nxt = next(self._messages, None)
            if nxt is None:
                # stream (if selected) not present; read() will raise EOFError
                return
            _, _, message = nxt
            record = json.loads(message.data)
            sensor_id = record["sensor"]["sensor_id"]
            if self._stream is not None and sensor_id != self._stream:
                continue
            self._pending = record
            sensor = record["sensor"]
            self._descriptor = SensorDescriptor(
                sensor_id=sensor_id,
                vendor=sensor["vendor"],
                model=sensor["model"],
                modality=sensor["modality"],
                frame_id=sensor["frame_id"],
                sample_rate_hz=sensor["sample_rate_hz"],
                capabilities=frozenset(sensor["capabilities"]),
                schema_version=sensor.get("schema_version", "1.0"),
            )
            self._resolved_stream = sensor_id

    def read(self) -> TactileObservation:
        """Return the next observation of the selected stream; EOFError at end."""
        descriptor = self._descriptor
        if self._file is None or self._messages is None or descriptor is None:
            raise RuntimeError("read() requires open(); call open() first")
        while True:
            if self._pending is not None:
                record = self._pending
                self._pending = None
            else:
                nxt = next(self._messages, None)
                if nxt is None:
                    raise EOFError(f"{self._path.name}: recording exhausted")
                _, _, message = nxt
                record = json.loads(message.data)
            if record["sensor"]["sensor_id"] != self._resolved_stream:
                continue
            taxels = _decode_array(record.get("taxels"))
            image = _decode_array(record.get("tactile_image"))
            metadata = dict(record.get("metadata") or {})
            if taxels is None and image is None:
                metadata["replay_summaries"] = {
                    "taxels": record.get("taxels"),
                    "tactile_image": record.get("tactile_image"),
                }
            return TactileObservation(
                timestamp_ns=record["timestamp_ns"],
                sensor=descriptor,
                raw=record.get("raw"),
                calibration_id=record.get("calibration_id"),
                tactile_image=image,
                taxels=taxels,
                quality=dict(record.get("quality") or {}),
                metadata=metadata,
            )

    def close(self) -> None:
        if self._file is None:
            return
        self._file.close()
        self._file = None
        self._messages = None
