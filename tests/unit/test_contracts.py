import json

import numpy as np
import pytest

from tacstack import (
    CalibrationSpec,
    ModelManifest,
    SensorDescriptor,
    TactileEvent,
    TactileObservation,
)
from tacstack.core.serialization import to_debug_json


def test_raw_preserved_and_serializable(sensor: SensorDescriptor) -> None:
    raw = np.array([[1.0, 2.0]])
    observation = TactileObservation(123, sensor, raw, taxels=raw)
    assert observation.raw is raw
    payload = json.loads(to_debug_json(observation))
    assert payload["raw"] == [[1.0, 2.0]]
    assert payload["sensor"]["capabilities"] == ["taxel_force"]
    assert payload["timestamp_ns"] == 123


@pytest.mark.parametrize("timestamp", [-1, 1.5, True])
def test_invalid_timestamp(sensor: SensorDescriptor, timestamp: int) -> None:
    with pytest.raises(ValueError, match="timestamp_ns"):
        TactileObservation(timestamp, sensor, None)


@pytest.mark.parametrize("probability", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_probability(probability: float) -> None:
    with pytest.raises(ValueError, match="probability"):
        TactileEvent(0, "sensor", "slip", probability, "model", 0)


@pytest.mark.parametrize("latency", [-1, float("nan"), float("inf")])
def test_invalid_latency(latency: float) -> None:
    with pytest.raises(ValueError, match="latency_ms"):
        TactileEvent(0, "sensor", "slip", 0.5, "model", latency)


def test_capabilities(sensor: SensorDescriptor) -> None:
    manifest = ModelManifest("m", "0", "contact", frozenset({"taxel_force"}), 10, "python", "")
    manifest.validate_capabilities(sensor)
    incompatible = ModelManifest(
        "m", "0", "contact", frozenset({"tactile_image"}), 10, "python", ""
    )
    with pytest.raises(ValueError, match="tactile_image"):
        incompatible.validate_capabilities(sensor)


def test_mutable_defaults_are_isolated(sensor: SensorDescriptor) -> None:
    first = TactileObservation(0, sensor, None)
    second = TactileObservation(0, sensor, None)
    first.metadata["example"] = True
    assert second.metadata == {}


def test_debug_rejects_unsupported_raw(sensor: SensorDescriptor) -> None:
    with pytest.raises(TypeError, match="Unsupported"):
        to_debug_json(TactileObservation(0, sensor, object()))
    with pytest.raises(ValueError):
        to_debug_json({"value": float("nan")})


def test_calibration_provenance() -> None:
    calibration = CalibrationSpec("c0", "sensor", "identity", {"scale": 1.0})
    assert json.loads(to_debug_json(calibration))["parameters"]["scale"] == 1.0
