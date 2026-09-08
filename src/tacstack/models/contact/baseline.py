"""Deterministic threshold baseline for contact_begin / contact_end events.

A heuristic, not a learned model: per-frame activity (mean magnitude of the
tactile payload) maps through a logistic to a probability, and a hysteresis
state machine emits edge-triggered ``contact_begin`` / ``contact_end`` events.
Defaults are uncalibrated; tune center / gain / thresholds per sensor (Phase 4
tracks cross-sensor calibration). ``latency_ms`` on returned events is the
wall time of the infer call itself; the Runtime wrapper re-stamps it with the
same measurement so callers see one consistent definition.
"""

from collections.abc import Sequence
from math import exp, isfinite
from time import perf_counter

from tacstack.core import EventKind, ModelManifest, TactileEvent, TactileObservation
from tacstack.models._signal import activity


def contact_baseline_manifest() -> ModelManifest:
    return ModelManifest(
        model_id="contact-baseline",
        version="0.1.0",
        task="contact",
        required_capabilities=frozenset(),
        window_ms=100,
        runtime="builtin",
        artifact_uri="builtin://tacstack/contact-baseline",
    )


class ContactHysteresis:
    """Rising/falling threshold state machine; edge-triggered transitions.

    Shared by the builtin logistic scorer and the ONNX backend so both emit
    exactly the same event sequence for the same score sequence.
    """

    def __init__(self, *, on_threshold: float = 0.6, off_threshold: float = 0.4) -> None:
        if not 0 < off_threshold < on_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 < off_threshold < on_threshold <= 1; "
                f"got off={off_threshold}, on={on_threshold}"
            )
        self._on = on_threshold
        self._off = off_threshold
        self._in_contact = False

    def update(self, probability: float) -> EventKind | None:
        """Feed one score; return the transition kind or None when silent."""
        if not self._in_contact and probability >= self._on:
            self._in_contact = True
            return "contact_begin"
        if self._in_contact and probability <= self._off:
            self._in_contact = False
            return "contact_end"
        return None


class ContactBaseline:
    """Logistic activity score with a hysteresis state machine.

    One instance replays one stream: the hysteresis state (whether
    ``contact_begin`` has been emitted and ``contact_end`` is awaited) lives
    here, so sharing an instance across streams would interleave their states.
    """

    #: payload capabilities this model can consume (any-of semantics)
    accepted_capabilities = frozenset({"tactile_image", "taxel_force"})

    def __init__(
        self,
        *,
        on_threshold: float = 0.6,
        off_threshold: float = 0.4,
        center: float = 0.5,
        gain: float = 12.0,
        model_id: str = "contact-baseline",
    ) -> None:
        if not 0 < off_threshold < on_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 < off_threshold < on_threshold <= 1; "
                f"got off={off_threshold}, on={on_threshold}"
            )
        if not isfinite(center):
            raise ValueError("center must be finite")
        if not isfinite(gain) or gain <= 0:
            raise ValueError("gain must be finite and positive")
        self._on = on_threshold
        self._off = off_threshold
        self._center = center
        self._gain = gain
        self._hysteresis = ContactHysteresis(on_threshold=on_threshold, off_threshold=off_threshold)
        self._manifest = ModelManifest(
            model_id=model_id,
            version="0.1.0",
            task="contact",
            required_capabilities=frozenset(),
            window_ms=100,
            runtime="builtin",
            artifact_uri=f"builtin://tacstack/{model_id}",
        )

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def probability(self, observation: TactileObservation) -> float:
        """Logistic mapping of the frame activity to [0, 1]."""
        value = activity(observation)
        return 1.0 / (1.0 + exp(-self._gain * (value - self._center)))

    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]:
        """Score the newest frame and return transition events (possibly none)."""
        if not window:
            return []
        observation = window[-1]
        started = perf_counter()
        value = activity(observation)
        probability = 1.0 / (1.0 + exp(-self._gain * (value - self._center)))
        metadata = {
            "activity_value": value,
            "on_threshold": self._on,
            "off_threshold": self._off,
            "oxt_frame_index": observation.metadata.get("oxt_frame_index"),
        }
        events: list[TactileEvent] = []
        kind = self._hysteresis.update(probability)
        if kind is not None:
            events.append(self._event(observation, kind, probability, metadata, started))
        return events

    def _event(
        self,
        observation: TactileObservation,
        kind: EventKind,
        probability: float,
        metadata: dict[str, object],
        started: float,
    ) -> TactileEvent:
        return TactileEvent(
            timestamp_ns=observation.timestamp_ns,
            sensor_id=observation.sensor.sensor_id,
            kind=kind,
            probability=probability,
            model_id=self._manifest.model_id,
            latency_ms=(perf_counter() - started) * 1000.0,
            region=None,
            metadata=metadata,
        )
