"""Blocking adapter contract; EOF and lifecycle are explicit."""

from collections.abc import Iterator
from typing import Protocol

from tacstack.core import SensorDescriptor, TactileObservation


class TactileAdapter(Protocol):
    def descriptor(self) -> SensorDescriptor: ...
    def open(self) -> None: ...
    def close(self) -> None: ...
    def read(self) -> TactileObservation:
        """Read one sample. Raise EOFError on exhausted replay; other errors propagate."""
        ...


def observations(adapter: TactileAdapter) -> Iterator[TactileObservation]:
    """Iterate an already-open adapter. The caller owns open/close."""
    while True:
        try:
            observation = adapter.read()
        except EOFError:
            return
        yield observation
