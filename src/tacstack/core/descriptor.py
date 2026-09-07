"""Sensor identity and declared capabilities."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SensorDescriptor:
    sensor_id: str
    vendor: str
    model: str
    modality: str
    frame_id: str
    sample_rate_hz: float | None
    capabilities: frozenset[str]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.sensor_id.strip():
            raise ValueError("sensor_id must not be empty")
        if self.sample_rate_hz is not None:
            if not isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
                raise ValueError("sample_rate_hz must be finite and positive")
