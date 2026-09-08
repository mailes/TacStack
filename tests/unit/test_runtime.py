"""Unit tests for WindowBuffer and the Runtime event loop."""

import numpy as np
import pytest

from tacstack import SensorDescriptor, TactileObservation
from tacstack.models import builtin_model
from tacstack.runtime.buffer import WindowBuffer
from tacstack.runtime.pipeline import Runtime


@pytest.fixture
def sensor() -> SensorDescriptor:
    return SensorDescriptor(
        "fixture", "test", "taxel", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
    )


def _observation(sensor: SensorDescriptor, index: int, value: float) -> TactileObservation:
    return TactileObservation(
        timestamp_ns=index * 1_000_000_000,
        sensor=sensor,
        raw=None,
        taxels=np.full((1, 6), value, dtype=np.float64),
        metadata={"oxt_frame_index": index},
    )


def test_buffer_slides_and_keeps_newest(sensor: SensorDescriptor) -> None:
    buffer = WindowBuffer(2)
    assert len(buffer) == 0 and not buffer.full()
    buffer.push(_observation(sensor, 0, 0.1))
    buffer.push(_observation(sensor, 1, 0.2))
    assert buffer.full() and buffer.size == 2
    buffer.push(_observation(sensor, 2, 0.3))
    window = buffer.window()
    assert [o.timestamp_ns for o in window] == [1_000_000_000, 2_000_000_000]


def test_buffer_rejects_invalid_size() -> None:
    with pytest.raises(ValueError, match="size must be"):
        WindowBuffer(0)
    with pytest.raises(ValueError, match="size must be"):
        WindowBuffer(True)  # bool is not a valid size


def test_runtime_stamps_latency_and_event_fields(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact", on_threshold=0.6, off_threshold=0.2)
    runtime = Runtime(model, window_frames=1)
    events = runtime.process(_observation(sensor, 0, 0.9))
    assert len(events) == 1
    event = events[0]
    assert event.kind == "contact_begin"
    assert event.model_id == "contact-baseline"
    assert event.sensor_id == "fixture"
    assert event.latency_ms >= 0.0
    assert event.metadata["activity_value"] == pytest.approx(0.9)


def test_runtime_events_generator_yields_in_order(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact", on_threshold=0.9, off_threshold=0.2)
    runtime = Runtime(model, window_frames=1)
    stream = [_observation(sensor, i, 0.95 if i % 2 == 0 else 0.0) for i in range(4)]
    kinds = [event.kind for event in runtime.events(stream)]
    assert kinds == ["contact_begin", "contact_end", "contact_begin", "contact_end"]


def test_runtime_requires_positive_window(sensor: SensorDescriptor) -> None:
    with pytest.raises(ValueError, match="size must be"):
        Runtime(builtin_model("contact"), window_frames=0)


def test_model_latency_and_runtime_latency_are_both_measured(sensor: SensorDescriptor) -> None:
    # models emit the wall time of their own infer call; the Runtime re-stamps
    # the same measurement so callers see one consistent latency definition.
    # Fresh instances per call: the hysteresis state lives in the model.
    observation = _observation(sensor, 0, 0.9)
    direct = builtin_model("contact").infer([observation])
    stamped = Runtime(builtin_model("contact"), window_frames=1).process(observation)
    assert direct[0].latency_ms >= 0.0
    assert stamped[0].latency_ms >= 0.0
    assert stamped[0].kind == direct[0].kind
