"""Deterministic temporal frame-difference baseline for micro_slip / slip.

A heuristic, not a learned model: the mean absolute difference between the
last two tactile frames of the window maps through a logistic to a slip
score. Events are edge-triggered on rising threshold crossings, so a
sustained slip emits one event, not one per frame; when the score drops back
below the micro threshold the state resets and a later rise re-emits.
Requires a window of at least two frames (Runtime ``window_frames >= 2``).
``latency_ms`` on returned events is the wall time of the infer call itself;
the Runtime wrapper re-stamps it with the same measurement.
"""

from collections.abc import Sequence
from math import exp, isfinite
from time import perf_counter

import numpy as np

from tacstack.core import EventKind, ModelManifest, TactileEvent, TactileObservation
from tacstack.models._signal import magnitude_frame, tactile_array


def slip_baseline_manifest() -> ModelManifest:
    return ModelManifest(
        model_id="slip-baseline",
        version="0.1.0",
        task="slip",
        required_capabilities=frozenset(),
        window_ms=200,
        runtime="builtin",
        artifact_uri="builtin://tacstack/slip-baseline",
    )


class SlipBaseline:
    """Frame-difference score with rising-edge event emission.

    One instance replays one stream for the same state-isolation reasons as
    ContactBaseline.
    """

    def __init__(
        self,
        *,
        micro_threshold: float = 0.4,
        slip_threshold: float = 0.7,
        center: float = 0.05,
        gain: float = 30.0,
        model_id: str = "slip-baseline",
    ) -> None:
        if not 0 < micro_threshold < slip_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 < micro_threshold < slip_threshold <= 1; "
                f"got micro={micro_threshold}, slip={slip_threshold}"
            )
        if not isfinite(center):
            raise ValueError("center must be finite")
        if not isfinite(gain) or gain <= 0:
            raise ValueError("gain must be finite and positive")
        self._micro = micro_threshold
        self._slip = slip_threshold
        self._center = center
        self._gain = gain
        self._manifest = ModelManifest(
            model_id=model_id,
            version="0.1.0",
            task="slip",
            required_capabilities=frozenset(),
            window_ms=200,
            runtime="builtin",
            artifact_uri=f"builtin://tacstack/{model_id}",
        )
        self._above_micro = False
        self._above_slip = False

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def score(self, previous: TactileObservation, current: TactileObservation) -> float:
        """Logistic mapping of the mean absolute frame difference to [0, 1]."""
        return self._diff_score(previous, current)[1]

    def _diff_score(
        self, previous: TactileObservation, current: TactileObservation
    ) -> tuple[float, float]:
        diff = float(
            np.abs(
                magnitude_frame(tactile_array(current)) - magnitude_frame(tactile_array(previous))
            ).mean()
        )
        probability = 1.0 / (1.0 + exp(-self._gain * (diff - self._center)))
        return diff, probability

    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]:
        """Compare the two newest frames and return rising-edge events."""
        if len(window) < 2:
            return []
        previous, current = window[-2], window[-1]
        started = perf_counter()
        diff, probability = self._diff_score(previous, current)
        above_micro = probability >= self._micro
        above_slip = probability >= self._slip
        metadata = {
            "diff_value": diff,
            "micro_threshold": self._micro,
            "slip_threshold": self._slip,
            "oxt_frame_index": current.metadata.get("oxt_frame_index"),
        }
        events: list[TactileEvent] = []
        kind: EventKind | None = None
        if above_slip and not self._above_slip:
            kind = "slip"
        elif above_micro and not self._above_micro:
            kind = "micro_slip"
        if kind is not None:
            events.append(
                TactileEvent(
                    timestamp_ns=current.timestamp_ns,
                    sensor_id=current.sensor.sensor_id,
                    kind=kind,
                    probability=probability,
                    model_id=self._manifest.model_id,
                    latency_ms=(perf_counter() - started) * 1000.0,
                    region=None,
                    metadata=metadata,
                )
            )
        self._above_micro = above_micro
        self._above_slip = above_slip
        return events
