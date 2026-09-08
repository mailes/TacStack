"""Inference protocol plus the frame-buffered Runtime event loop.

``TactileModel`` is the protocol every model implements; ``Runtime`` slides a
``WindowBuffer`` over an observation stream, calls the model once per frame,
and stamps ``latency_ms`` on every emitted event with the wall time of the
``infer`` call that produced it (models report the same measurement, callers
get one consistent definition). The intended control-side loop is::

    runtime = Runtime(model, window_frames=2)
    for event in runtime.events(observations(adapter)):
        if event.kind == "slip":
            ...
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import replace
from time import perf_counter
from typing import Protocol

from tacstack.core import ModelManifest, TactileEvent, TactileObservation
from tacstack.runtime.buffer import WindowBuffer


class TactileModel(Protocol):
    @property
    def manifest(self) -> ModelManifest: ...
    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]: ...


class Runtime:
    """Buffer observations, run the model per frame, yield events.

    One Runtime instance drives one model over one stream: models keep their
    event state machines per instance, and the window is per stream too.
    """

    def __init__(self, model: TactileModel, *, window_frames: int = 2) -> None:
        self._model = model
        self._buffer = WindowBuffer(window_frames)

    @property
    def model(self) -> TactileModel:
        return self._model

    @property
    def window_frames(self) -> int:
        return self._buffer.size

    def process(self, observation: TactileObservation) -> list[TactileEvent]:
        """Push one observation and return the events the model emits for it."""
        self._buffer.push(observation)
        started = perf_counter()
        events = self._model.infer(self._buffer.window())
        elapsed_ms = (perf_counter() - started) * 1000.0
        return [replace(event, latency_ms=elapsed_ms) for event in events]

    def events(self, source: Iterable[TactileObservation]) -> Iterator[TactileEvent]:
        """Stream observations through the model, yielding events as they come."""
        for observation in source:
            yield from self.process(observation)
