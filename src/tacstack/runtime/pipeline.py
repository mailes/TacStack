"""Inference protocol. Pipeline execution is planned for Phase 3."""

from collections.abc import Sequence
from typing import Protocol

from tacstack.core import ModelManifest, TactileEvent, TactileObservation


class TactileModel(Protocol):
    @property
    def manifest(self) -> ModelManifest: ...
    def infer(self, window: Sequence[TactileObservation]) -> list[TactileEvent]: ...
