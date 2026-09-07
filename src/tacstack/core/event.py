"""Version-zero semantic event contract; not a control safety guarantee."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal, get_args

import numpy as np
import numpy.typing as npt

EventKind = Literal[
    "contact_begin",
    "contact_end",
    "micro_slip",
    "slip",
    "stable_grasp",
    "unstable_grasp",
    "over_force",
]


@dataclass(frozen=True)
class TactileEvent:
    timestamp_ns: int
    sensor_id: str
    kind: EventKind
    probability: float
    model_id: str
    latency_ms: float
    region: str | None = None
    vector: npt.NDArray[np.float64] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.timestamp_ns) is not int or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative Python integer")
        if not self.sensor_id.strip() or not self.model_id.strip():
            raise ValueError("sensor_id and model_id must not be empty")
        if self.kind not in get_args(EventKind):
            raise ValueError("unsupported event kind")
        if not isfinite(self.probability) or not 0 <= self.probability <= 1:
            raise ValueError("probability must be finite and in [0, 1]")
        if not isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms must be finite and non-negative")
        if self.vector is not None:
            # A frozen dataclass does not deep-freeze arrays: keep a read-only snapshot so
            # later writes to the producer's array cannot change an already-created event.
            snapshot = np.array(self.vector, copy=True)
            snapshot.setflags(write=False)
            object.__setattr__(self, "vector", snapshot)
