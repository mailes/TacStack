"""MCAP export of TactileObservation streams as JSON-schema messages.

Contract:
- One JSON message per observation on the channel ``tacstack/observations``,
  using a registered JSON schema (``tacstack.tactile_observation.v1``), so the
  recording opens directly in Foxglove and other MCAP tools.
- Bulk payloads are summarized, not embedded: image/taxel arrays appear as
  shape + dtype + summary statistics. This keeps the record small and the
  export memory-stable for long episodes; the full-precision raw arrays remain
  in their source archive, and Rerun visualization (roadmap Issue #4) reads
  them from observations directly.
- ``log_time`` / ``publish_time`` use the observation's ``timestamp_ns``; when
  the adapter runs in the index timestamp domain those values are index-scaled,
  which preserves ordering but is not wall-clock time.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from mcap.writer import Writer

from tacstack.core.serialization import to_debug_dict

TOPIC = "tacstack/observations"
SCHEMA_NAME = "tacstack.tactile_observation.v1"
PROFILE = "tacstack"

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "title": SCHEMA_NAME,
    "description": "One TacStack TactileObservation; bulk arrays are summarized, not embedded.",
    "properties": {
        "timestamp_ns": {"type": "integer"},
        "sensor": {"type": "object"},
        "raw": {"type": "object"},
        "calibration_id": {"type": ["string", "null"]},
        "tactile_image": {
            "type": ["object", "null"],
            "description": "shape/dtype/summary of the tactile image stack",
        },
        "taxels": {
            "type": ["object", "null"],
            "description": "shape/dtype/summary of the taxel frame",
        },
        "quality": {"type": "object"},
        "metadata": {"type": "object"},
    },
    "required": ["timestamp_ns", "sensor"],
}


@dataclass(frozen=True)
class McapExportSummary:
    """What one export produced; cheap to print in CLI output."""

    messages: int
    first_timestamp_ns: int | None
    last_timestamp_ns: int | None
    path: Path


def _summarize_array(value: Any) -> dict[str, Any] | None:
    """Describe a bulk array without embedding it; scalar-free and JSON-safe."""
    if value is None:
        return None
    flat = np.asarray(value)
    return {
        "shape": list(flat.shape),
        "dtype": str(flat.dtype),
        "min": float(flat.min()) if flat.size else None,
        "max": float(flat.max()) if flat.size else None,
        "mean": float(flat.mean()) if flat.size else None,
    }


def observation_record(observation: Any) -> dict[str, Any]:
    """Build the JSON payload for one observation (schema SCHEMA_NAME)."""
    return {
        "timestamp_ns": observation.timestamp_ns,
        "sensor": to_debug_dict(observation.sensor),
        "raw": to_debug_dict(observation.raw),
        "calibration_id": observation.calibration_id,
        "tactile_image": _summarize_array(observation.tactile_image),
        "taxels": _summarize_array(observation.taxels),
        "quality": to_debug_dict(observation.quality),
        "metadata": to_debug_dict(observation.metadata),
    }


def write_episode_mcap(observations: Iterable[Any], out: str | Path) -> McapExportSummary:
    """Write observations as JSON messages; returns a summary for CLI output."""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    messages = 0
    first_ts: int | None = None
    last_ts: int | None = None
    with out_path.open("wb") as stream:
        writer = Writer(stream)
        writer.start(profile=PROFILE, library="tacstack")
        schema_id = writer.register_schema(
            name=SCHEMA_NAME, encoding="jsonschema", data=json.dumps(_SCHEMA).encode("utf-8")
        )
        channel_id = writer.register_channel(
            topic=TOPIC, message_encoding="json", schema_id=schema_id
        )
        for observation in observations:
            record = observation_record(observation)
            payload = json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8")
            timestamp = observation.timestamp_ns
            writer.add_message(
                channel_id=channel_id,
                log_time=timestamp,
                publish_time=timestamp,
                sequence=messages,
                data=payload,
            )
            messages += 1
            first_ts = timestamp if first_ts is None else first_ts
            last_ts = timestamp
        writer.finish()
    return McapExportSummary(
        messages=messages, first_timestamp_ns=first_ts, last_timestamp_ns=last_ts, path=out_path
    )
