"""ONNX backend tests: graph export, builtin equivalence, event sequences."""

from pathlib import Path

import numpy as np
import pytest

from tacstack import SensorDescriptor, TactileObservation
from tacstack.models import builtin_model
from tacstack.runtime.onnx_backend import (
    OnnxContactModel,
    OnnxSlipModel,
    export_contact_scoring,
    export_slip_scoring,
)


@pytest.fixture
def sensor() -> SensorDescriptor:
    return SensorDescriptor(
        "fixture", "test", "taxel", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
    )


def _observation(
    sensor: SensorDescriptor, index: int, value: float, *, shape: tuple[int, ...] = (2, 4, 4, 3)
) -> TactileObservation:
    # matrix shape by default exercises the magnitude path shared by builtin
    # and ONNX; pass a vector shape to probe the micro/slip split directly
    return TactileObservation(
        timestamp_ns=index * 1_000_000_000,
        sensor=sensor,
        raw=None,
        taxels=np.full(shape, value, dtype=np.float64),
        metadata={"oxt_frame_index": index},
    )


def test_contact_probability_matches_builtin_within_float32(
    tmp_path: Path, sensor: SensorDescriptor
) -> None:
    artifact = export_contact_scoring(tmp_path / "contact.onnx", center=0.5, gain=12.0)
    onnx_model = OnnxContactModel(artifact)
    builtin = builtin_model("contact", center=0.5, gain=12.0)
    for value in (0.0, 0.3, 0.5, 0.7, 0.95):
        observation = _observation(sensor, 0, value)
        assert onnx_model.probability(observation) == pytest.approx(
            builtin.probability(observation), abs=1e-5
        )


def test_slip_probability_matches_builtin_within_float32(
    tmp_path: Path, sensor: SensorDescriptor
) -> None:
    artifact = export_slip_scoring(tmp_path / "slip.onnx", center=0.05, gain=30.0)
    onnx_model = OnnxSlipModel(artifact)
    builtin = builtin_model("slip", center=0.05, gain=30.0)
    series = [0.0, 0.02, 0.06, 0.2, 0.2, 0.0, 0.06]
    for i in range(1, len(series)):
        previous = _observation(sensor, i - 1, series[i - 1])
        current = _observation(sensor, i, series[i])
        assert onnx_model.score(previous, current) == pytest.approx(
            builtin.score(previous, current), abs=1e-5
        )


def test_contact_event_sequence_matches_builtin(tmp_path: Path, sensor: SensorDescriptor) -> None:
    artifact = export_contact_scoring(tmp_path / "contact.onnx")
    onnx_model = OnnxContactModel(artifact)
    builtin = builtin_model("contact")
    series = [0.0, 0.9, 0.9, 0.0, 0.0, 0.9]
    kinds_onnx: list[str] = []
    kinds_builtin: list[str] = []
    for i, value in enumerate(series):
        observation = _observation(sensor, i, value)
        kinds_onnx.extend(event.kind for event in onnx_model.infer([observation]))
        kinds_builtin.extend(event.kind for event in builtin.infer([observation]))
    assert kinds_onnx == kinds_builtin == ["contact_begin", "contact_end", "contact_begin"]


def test_slip_event_sequence_matches_builtin(tmp_path: Path, sensor: SensorDescriptor) -> None:
    artifact = export_slip_scoring(tmp_path / "slip.onnx")
    onnx_model = OnnxSlipModel(artifact)
    builtin = builtin_model("slip")
    # vector shape: diff = |value delta| with no axes amplification, so the
    # micro (0.4) and slip (0.7) thresholds split the rising edges cleanly
    series = [0.0, 0.0, 0.06, 0.2, 0.2, 0.0, 0.06, 0.2]
    kinds_onnx: list[str] = []
    kinds_builtin: list[str] = []
    for i in range(1, len(series)):
        previous = _observation(sensor, i - 1, series[i - 1], shape=(1, 6))
        current = _observation(sensor, i, series[i], shape=(1, 6))
        kinds_onnx.extend(event.kind for event in onnx_model.infer([previous, current]))
        kinds_builtin.extend(event.kind for event in builtin.infer([previous, current]))
    assert kinds_onnx == kinds_builtin
    # micro on the slow 0->0.06 rise; every fast rise (0->0.2, 0.06->0.2) and
    # the release (0.2->0) exceed the slip threshold, matching builtin exactly
    assert kinds_onnx == ["micro_slip", "slip", "slip", "slip"]


def test_onnx_manifest_records_artifact_and_runtime(tmp_path: Path) -> None:
    artifact = export_contact_scoring(tmp_path / "contact.onnx")
    model = OnnxContactModel(artifact, model_id="custom-id")
    assert model.manifest.runtime == "onnxruntime"
    assert model.manifest.artifact_uri == str(artifact)
    assert model.manifest.model_id == "custom-id"


def test_missing_artifact_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        OnnxContactModel(tmp_path / "missing.onnx")
