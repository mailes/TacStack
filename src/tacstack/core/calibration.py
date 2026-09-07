"""Calibration provenance; does not implement calibration algorithms."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalibrationSpec:
    calibration_id: str
    sensor_id: str
    method: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not all(x.strip() for x in (self.calibration_id, self.sensor_id, self.method)):
            raise ValueError("calibration_id, sensor_id and method must not be empty")
