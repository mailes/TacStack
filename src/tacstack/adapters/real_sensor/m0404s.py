"""M0404S (洛城电子 / 冠拓电子) 16-point tactile array protocol parser.

Frame layout (35 bytes, vendor manual section 3.4, serial version, active
reporting over 115200 8N1):

- B1: frame header ``0xAA``
- B2: packet counter (increments per frame, mod 256)
- B3..B34: 16 sensing points x 2 bytes, unsigned big-endian (high byte first)
- B35: low byte of the arithmetic sum of B1..B34

The manual's worked example frame (``AA 01 00 4E ... 08 3C``) is the golden
fixture in ``tests/unit/test_m0404s.py``. One doc erratum to be aware of:
the manual's decode line prints point 13 as "0*256+37=37" - the byte is
``0x37``, i.e. decimal 55; the parser follows the bytes, not the prose.
This module is the pure protocol layer; the pyserial live adapter that feeds
it into ``TactileObservation`` lands when the hardware arrives (Phase 5).
"""

from dataclasses import dataclass

FRAME_HEADER = 0xAA
FRAME_LENGTH = 35
POINT_COUNT = 16
_CHECKSUM_SPAN = FRAME_LENGTH - 1  # B1..B34


@dataclass(frozen=True)
class M0404SFrame:
    """One decoded M0404S frame: packet counter plus 16 point values."""

    packet: int
    points: tuple[int, ...]


def checksum(data: bytes) -> int:
    """Low byte of the arithmetic sum over ``data`` (vendor checksum rule)."""
    return sum(data) & 0xFF


def parse_frame(frame: bytes) -> M0404SFrame:
    """Decode one 35-byte frame; ValueError on length, header or checksum mismatch."""
    if len(frame) != FRAME_LENGTH:
        raise ValueError(f"frame must be exactly {FRAME_LENGTH} bytes, got {len(frame)}")
    if frame[0] != FRAME_HEADER:
        raise ValueError(f"frame header must be 0xAA, got 0x{frame[0]:02X}")
    if checksum(frame[:_CHECKSUM_SPAN]) != frame[_CHECKSUM_SPAN]:
        raise ValueError(
            f"frame checksum mismatch: expected 0x{checksum(frame[:_CHECKSUM_SPAN]):02X}, "
            f"got 0x{frame[_CHECKSUM_SPAN]:02X}"
        )
    points = tuple(
        int.from_bytes(frame[2 + 2 * i : 4 + 2 * i], byteorder="big") for i in range(POINT_COUNT)
    )
    return M0404SFrame(packet=frame[1], points=points)


class M0404SStreamParser:
    """Byte-stream oriented parser for a live serial feed.

    ``feed()`` accepts whatever bytes arrived and returns every complete,
    checksum-valid frame they contain. Resynchronization scans forward to the
    next ``0xAA`` after any garbage or bad-checksum candidate, so a corrupted
    frame only costs its own bytes, never the ones after it.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.frames_ok = 0
        self.frames_bad = 0

    def feed(self, data: bytes | bytearray) -> list[M0404SFrame]:
        self._buffer.extend(data)
        frames: list[M0404SFrame] = []
        while len(self._buffer) >= FRAME_LENGTH:
            if self._buffer[0] != FRAME_HEADER:
                resync = self._buffer.find(bytes([FRAME_HEADER]), 1)
                offset = resync if resync != -1 else len(self._buffer) - 1
                del self._buffer[:offset]
                self.frames_bad += 1
                continue
            try:
                frames.append(parse_frame(bytes(self._buffer[:FRAME_LENGTH])))
            except ValueError:
                self.frames_bad += 1
                del self._buffer[:1]
                continue
            del self._buffer[:FRAME_LENGTH]
            self.frames_ok += 1
        return frames
