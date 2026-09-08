"""Unit tests for the built-in contact and slip baseline models."""

import numpy as np
import pytest

from tacstack import SensorDescriptor, TactileObservation
from tacstack.models import builtin_model
from tacstack.models.contact import contact_baseline_manifest
from tacstack.models.slip import slip_baseline_manifest


@pytest.fixture
def sensor() -> SensorDescriptor:
    return SensorDescriptor(
        "fixture", "test", "taxel", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
    )


def _observation(
    sensor: SensorDescriptor, index: int, taxels: np.ndarray | float
) -> TactileObservation:
    array = (
        np.full((1, 6), taxels, dtype=np.float64)
        if isinstance(taxels, float)
        else np.asarray(taxels, dtype=np.float64)
    )
    return TactileObservation(
        timestamp_ns=index * 1_000_000_000,
        sensor=sensor,
        raw=None,
        taxels=array,
        metadata={"oxt_frame_index": index},
    )


def test_contact_hysteresis_emits_edges_once(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact", on_threshold=0.9, off_threshold=0.2, center=0.5, gain=12.0)
    assert model.infer([_observation(sensor, 0, 0.0)]) == []  # below: no event
    begin = model.infer([_observation(sensor, 1, 0.9)])
    assert [e.kind for e in begin] == ["contact_begin"]
    assert model.infer([_observation(sensor, 2, 0.9)]) == []  # sustained: silent
    end = model.infer([_observation(sensor, 3, 0.0)])
    assert [e.kind for e in end] == ["contact_end"]
    assert model.infer([_observation(sensor, 4, 0.0)]) == []
    begin_again = model.infer([_observation(sensor, 5, 0.9)])
    assert [e.kind for e in begin_again] == ["contact_begin"]  # state reset works


def test_contact_probability_is_monotonic_in_activity(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact")
    low = model.probability(_observation(sensor, 0, 0.2))
    mid = model.probability(_observation(sensor, 1, 0.5))
    high = model.probability(_observation(sensor, 2, 0.9))
    assert 0.0 <= low < mid < high <= 1.0


def test_contact_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="0 < off_threshold < on_threshold"):
        builtin_model("contact", on_threshold=0.2, off_threshold=0.9)
    with pytest.raises(ValueError, match="gain must be"):
        builtin_model("contact", gain=-1.0)


def test_contact_requires_tactile_payload(sensor: SensorDescriptor) -> None:
    model = builtin_model("contact")
    bare = TactileObservation(0, sensor, None)
    with pytest.raises(ValueError, match="no tactile payload"):
        model.infer([bare])


def test_contact_manifest_declares_builtin_runtime() -> None:
    manifest = contact_baseline_manifest()
    assert manifest.model_id == "contact-baseline"
    assert manifest.task == "contact"
    assert manifest.runtime == "builtin"
    assert manifest.artifact_uri.startswith("builtin://")


def test_slip_silent_on_constant_frames(sensor: SensorDescriptor) -> None:
    model = builtin_model("slip")
    frames = [_observation(sensor, i, 0.5) for i in range(4)]
    events: list = []
    for i in range(len(frames)):
        window = frames[max(0, i - 1) : i + 1]
        events.extend(model.infer(window))
    assert events == []


def test_slip_rising_edges_emit_micro_then_slip(sensor: SensorDescriptor) -> None:
    model = builtin_model("slip", micro_threshold=0.4, slip_threshold=0.7, gain=30.0)
    # slow ramp: score first crosses micro, later crosses slip
    series = [0.0, 0.0, 0.02, 0.06, 0.2, 0.2, 0.0, 0.0, 0.06, 0.2]
    events: list[str] = []
    for i in range(1, len(series)):
        window = [_observation(sensor, i - 1, series[i - 1]), _observation(sensor, i, series[i])]
        events.extend(event.kind for event in model.infer(window))
    assert events[0] == "micro_slip"
    assert "slip" in events
    # after the drop to zero the flags reset, so a later rise re-emits
    assert events.count("micro_slip") >= 2


def test_slip_requires_two_frames(sensor: SensorDescriptor) -> None:
    model = builtin_model("slip")
    assert model.infer([_observation(sensor, 0, 0.9)]) == []


def test_slip_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="0 < micro_threshold < slip_threshold"):
        builtin_model("slip", micro_threshold=0.9, slip_threshold=0.4)


def test_slip_manifest_declares_slip_task() -> None:
    manifest = slip_baseline_manifest()
    assert manifest.model_id == "slip-baseline"
    assert manifest.task == "slip"
    assert manifest.window_ms == 200


def test_builtin_factory_rejects_unknown_names() -> None:
    with pytest.raises(KeyError, match="unknown built-in model"):
        builtin_model("grief")
