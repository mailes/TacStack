"""Run with uv run python examples/contract_demo.py; synthetic data only."""

import numpy as np

from tacstack import SensorDescriptor, TactileObservation
from tacstack.core.serialization import to_debug_json

sensor = SensorDescriptor(
    "synthetic", "example", "fixture", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
)
observation = TactileObservation(timestamp_ns=0, sensor=sensor, raw=np.zeros((2, 3)))
print(to_debug_json(observation))
