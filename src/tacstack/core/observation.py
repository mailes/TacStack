"""Raw-first observation; arrays remain sensor-specific."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from tacstack.core.descriptor import SensorDescriptor


@dataclass
class TactileObservation:
    timestamp_ns: int
    sensor: SensorDescriptor
    raw: Any
    calibration_id: str | None = None
    tactile_image: npt.NDArray[Any] | None = None
    taxels: npt.NDArray[Any] | None = None
    taxel_positions_m: npt.NDArray[np.float64] | None = None
    wrench: npt.NDArray[np.float64] | None = None
    temperature_c: npt.NDArray[np.float64] | None = None
    imu: npt.NDArray[np.float64] | None = None
    quality: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.timestamp_ns) is not int or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative Python integer")
