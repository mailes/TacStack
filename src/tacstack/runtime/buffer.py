"""Frame-count sliding window for temporal models.

Window sizing is in frames for v0.1: FTP-1 timestamps are index-domain, so a
millisecond window would need a caller-supplied frame rate. ``window_ms`` on
ModelManifest stays the model-level declaration; callers derive
``window_frames`` from it when a frame rate is known.
"""

from collections import deque

from tacstack.core import TactileObservation


class WindowBuffer:
    """Fixed-size sliding window over the most recent observations."""

    def __init__(self, size: int) -> None:
        if type(size) is not int or size < 1:
            raise ValueError("size must be a positive Python integer")
        self._size = size
        self._items: deque[TactileObservation] = deque(maxlen=size)

    @property
    def size(self) -> int:
        return self._size

    def push(self, observation: TactileObservation) -> None:
        self._items.append(observation)

    def window(self) -> tuple[TactileObservation, ...]:
        """Current window contents, oldest first."""
        return tuple(self._items)

    def full(self) -> bool:
        return len(self._items) == self._size

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
