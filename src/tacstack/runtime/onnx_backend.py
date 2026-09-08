"""ONNX scoring artifacts and the onnxruntime inference backend.

The built-in baselines separate into a stateless scoring function and a
stateful event state machine. The scoring function is exported as a
hand-written ONNX graph (no PyTorch) with the logistic center/gain baked in
as initializers; the graph consumes the magnitude frame (see
``models._signal``) flattened to a float32 vector, so the artifact works for
any payload shape. The state machines (``ContactHysteresis`` /
``SlipEdgeTracker``) stay in Python and are shared with the builtin classes,
so builtin and ONNX models emit identical event sequences for identical
scores.

Artifacts pair with a ``ModelManifest`` whose ``runtime`` is
``"onnxruntime"`` and whose ``artifact_uri`` points at the ``.onnx`` file.
Requires the optional ``onnx`` extra (``uv sync --extra onnx``): ``onnx``
for export, ``onnxruntime`` for inference.
"""

from collections.abc import Sequence
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from tacstack.core import ModelManifest, TactileEvent, TactileObservation
from tacstack.models._signal import magnitude_frame, tactile_array
from tacstack.models.contact.baseline import ContactHysteresis
from tacstack.models.slip.baseline import SlipEdgeTracker

_OPSET = 17


def _logistic_model(
    graph_inputs: list[str],
    nodes: list[Any],
    outputs: list[str],
    center: float,
    gain: float,
    producer: str,
) -> Any:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    initializers = [
        numpy_helper.from_array(np.array(center, dtype=np.float32), "center"),
        numpy_helper.from_array(np.array(gain, dtype=np.float32), "gain"),
    ]
    input_defs = [
        helper.make_tensor_value_info(name, TensorProto.FLOAT, [None]) for name in graph_inputs
    ]
    output_defs = [helper.make_tensor_value_info(name, TensorProto.FLOAT, []) for name in outputs]
    graph = helper.make_graph(
        nodes,
        producer,
        input_defs,
        output_defs,
        initializer=initializers,
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", _OPSET)],
        producer_name="tacstack",
    )
    onnx.checker.check_model(model)
    return model


def export_contact_scoring(path: str | Path, *, center: float = 0.5, gain: float = 12.0) -> Path:
    """Export mean(|frame|) -> logistic(center, gain) as an ONNX graph."""
    if not isfinite(center):
        raise ValueError("center must be finite")
    if not isfinite(gain) or gain <= 0:
        raise ValueError("gain must be finite and positive")
    import onnx
    from onnx import helper

    nodes = [
        helper.make_node("Abs", ["frame"], ["abs"]),
        helper.make_node("ReduceMean", ["abs"], ["reduced"], axes=[0], keepdims=0),
        helper.make_node("Sub", ["reduced", "center"], ["shifted"]),
        helper.make_node("Mul", ["shifted", "gain"], ["scaled"]),
        helper.make_node("Sigmoid", ["scaled"], ["probability"]),
    ]
    model = _logistic_model(["frame"], nodes, ["probability"], center, gain, "tacstack.contact")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, out)
    return out


def export_slip_scoring(path: str | Path, *, center: float = 0.05, gain: float = 30.0) -> Path:
    """Export mean(|current - previous|) -> logistic(center, gain) as an ONNX graph."""
    if not isfinite(center):
        raise ValueError("center must be finite")
    if not isfinite(gain) or gain <= 0:
        raise ValueError("gain must be finite and positive")
    import onnx
    from onnx import helper

    nodes = [
        helper.make_node("Sub", ["current", "previous"], ["delta"]),
        helper.make_node("Abs", ["delta"], ["abs"]),
        helper.make_node("ReduceMean", ["abs"], ["reduced"], axes=[0], keepdims=0),
        helper.make_node("Sub", ["reduced", "center"], ["shifted"]),
        helper.make_node("Mul", ["shifted", "gain"], ["scaled"]),
        helper.make_node("Sigmoid", ["scaled"], ["probability"]),
    ]
    model = _logistic_model(
        ["previous", "current"], nodes, ["probability"], center, gain, "tacstack.slip"
    )
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, out)
    return out


def _inference_session(artifact: str | Path) -> Any:
    try:
        import onnxruntime as ort
    except ImportError as error:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            f"onnxruntime is not installed; run: uv sync --extra onnx ({error})"
        ) from error
    path = Path(artifact)
    if not path.exists():
        raise FileNotFoundError(f"ONNX artifact not found: {path}")
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _score(session: Any, observation: TactileObservation, feed_names: Sequence[str]) -> float:
    frames = {
        name: np.ascontiguousarray(
            magnitude_frame(tactile_array(observation)).reshape(-1), dtype=np.float32
        )
        for name in feed_names
    }
    (probability,) = session.run(["probability"], frames)
    return float(probability)


class OnnxContactModel:
    """Contact scoring from an ONNX artifact + the shared hysteresis machine."""

    #: payload capabilities this model can consume (any-of semantics)
    accepted_capabilities = frozenset({"tactile_image", "taxel_force"})

    def __init__(
        self,
        artifact: str | Path,
        *,
        on_threshold: float = 0.6,
        off_threshold: float = 0.4,
        model_id: str = "contact-onnx",
    ) -> None:
        self._artifact = str(artifact)
        self._session = _inference_session(artifact)
        self._hysteresis = ContactHysteresis(on_threshold=on_threshold, off_threshold=off_threshold)
        self._on = on_threshold
        self._off = off_threshold
        self._manifest = ModelManifest(
            model_id=model_id,
            version="0.1.0",
            task="contact",
            required_capabilities=frozenset(),
            window_ms=100,
            runtime="onnxruntime",
            artifact_uri=self._artifact,
        )

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def probability(self, observation: TactileObservation) -> float:
        return _score(self._session, observation, ["frame"])

    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]:
        """Score the newest frame and return transition events (possibly none)."""
        if not window:
            return []
        observation = window[-1]
        started = perf_counter()
        probability = self.probability(observation)
        kind = self._hysteresis.update(probability)
        if kind is None:
            return []
        event = TactileEvent(
            timestamp_ns=observation.timestamp_ns,
            sensor_id=observation.sensor.sensor_id,
            kind=kind,
            probability=probability,
            model_id=self._manifest.model_id,
            latency_ms=(perf_counter() - started) * 1000.0,
            region=None,
            metadata={
                "artifact": self._artifact,
                "calibration_id": observation.calibration_id,
                "on_threshold": self._on,
                "off_threshold": self._off,
                "oxt_frame_index": observation.metadata.get("oxt_frame_index"),
            },
        )
        return [event]


class OnnxSlipModel:
    """Slip scoring from an ONNX artifact + the shared rising-edge tracker."""

    #: payload capabilities this model can consume (any-of semantics)
    accepted_capabilities = frozenset({"tactile_image", "taxel_force"})

    def __init__(
        self,
        artifact: str | Path,
        *,
        micro_threshold: float = 0.4,
        slip_threshold: float = 0.7,
        model_id: str = "slip-onnx",
    ) -> None:
        self._artifact = str(artifact)
        self._session = _inference_session(artifact)
        self._tracker = SlipEdgeTracker(
            micro_threshold=micro_threshold, slip_threshold=slip_threshold
        )
        self._micro = micro_threshold
        self._slip = slip_threshold
        self._manifest = ModelManifest(
            model_id=model_id,
            version="0.1.0",
            task="slip",
            required_capabilities=frozenset(),
            window_ms=200,
            runtime="onnxruntime",
            artifact_uri=self._artifact,
        )

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def score(self, previous: TactileObservation, current: TactileObservation) -> float:
        frames = {
            "previous": np.ascontiguousarray(
                magnitude_frame(tactile_array(previous)).reshape(-1), dtype=np.float32
            ),
            "current": np.ascontiguousarray(
                magnitude_frame(tactile_array(current)).reshape(-1), dtype=np.float32
            ),
        }
        (probability,) = self._session.run(["probability"], frames)
        return float(probability)

    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]:
        """Compare the two newest frames and return rising-edge events."""
        if len(window) < 2:
            return []
        previous, current = window[-2], window[-1]
        started = perf_counter()
        probability = self.score(previous, current)
        kind = self._tracker.update(probability)
        if kind is None:
            return []
        event = TactileEvent(
            timestamp_ns=current.timestamp_ns,
            sensor_id=current.sensor.sensor_id,
            kind=kind,
            probability=probability,
            model_id=self._manifest.model_id,
            latency_ms=(perf_counter() - started) * 1000.0,
            region=None,
            metadata={
                "artifact": self._artifact,
                "calibration_id": current.calibration_id,
                "micro_threshold": self._micro,
                "slip_threshold": self._slip,
                "oxt_frame_index": current.metadata.get("oxt_frame_index"),
            },
        )
        return [event]
