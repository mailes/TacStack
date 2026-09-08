"""PaXini PX-6AX GEN3 UART protocol codec (user manual 2025-11, section 5.4).

The GEN3 speaks SPI / UART / IIC, selected by CS pin levels at power-on; the
单路串口转接板 ties CS low and bridges UART to a USB COM port at **921600
8N1**. UART is strictly request -> response: the host polls a register block
and the sensor answers one frame per request. This module is the pure codec
layer - frame building, parsing, LRC and register decoding - verified against
the manual's worked instruction examples; the pyserial polling adapter lands
with the hardware (Phase 5).

Frame rules (manual 5.4.2):
- request:  ``55 AA`` <len LE16> <addr> ``00`` <func> <start LE32> <len LE16>
  [data] <LRC>
- response: ``AA 55`` <len LE16> <addr> ``00`` <func> <start LE32> <len LE16>
  <status> [data] <LRC>
- ``len`` counts every byte from the device address through the last byte
  before LRC (the manual's example request is exactly 9)
- func: ``0x7B`` read / ``0x79`` write (user config), read frames set the
  high bit -> ``0xFB``
- LRC: two's complement of the byte sum of all preceding bytes (the manual's
  three worked examples - LRC CA/C9/C8 for device addresses 1/2/3 - pin this
  down exactly; a plain byte sum does not match)
- sensor force bytes: Fx/Fy signed, Fz unsigned, 1 LSB = 0.1 N
"""

import struct

UART_BAUDRATE = 921600
FUNC_WRITE_CONFIG = 0x79  # user configuration area (recalibrate switch etc.)
FUNC_READ_APP = 0x7B  # application area, read-only, supports continuous reads
ADDR_RESULTANT_FORCE = 1008  # resultant Fx, Fy, Fz - one byte each
ADDR_DISTRIBUTED_FORCE = 1038  # per-point Fx, Fy, Fz - three bytes per point
_REQUEST_HEADER = b"\x55\xaa"
_RESPONSE_HEADER = b"\xaa\x55"
_RESERVED = 0x00
_READ_FLAG = 0x80


def lrc(data: bytes) -> int:
    """Two's-complement LRC: frame bytes + LRC sum to zero mod 256."""
    return (-sum(data)) & 0xFF


def build_read_request(device: int, start: int, length: int) -> bytes:
    """Build a UART register-read request frame (manual 5.4.2, 请求帧)."""
    if not 0 <= device <= 255:
        raise ValueError("device must fit in one byte")
    if length <= 0:
        raise ValueError("length must be positive")
    body = bytes([device, _RESERVED, _READ_FLAG | FUNC_READ_APP])
    body += struct.pack("<IH", start, length)
    # the length field counts the bytes after it, excluding LRC (manual
    # example: 9 = addr + reserved + func + start(4) + length(2))
    frame = _REQUEST_HEADER + struct.pack("<H", len(body)) + body
    return frame + bytes([lrc(frame)])


def parse_response(frame: bytes) -> tuple[int, int, bytes]:
    """Parse one response frame; returns (device, start_address, data bytes).

    ValueError on header, length, function, status or LRC mismatch.
    """
    if len(frame) < 14:
        raise ValueError(f"response must be at least 14 bytes, got {len(frame)}")
    if frame[:2] != _RESPONSE_HEADER:
        raise ValueError("response header must be AA 55")
    (length,) = struct.unpack("<H", frame[2:4])
    if len(frame) != length + 5:
        raise ValueError(f"frame length field says {length}, got {len(frame) - 5} bytes")
    if frame[-1] != lrc(frame[:-1]):
        raise ValueError("response LRC mismatch")
    device = frame[4]
    (function,) = struct.unpack_from("<B", frame, 6)
    if function != _READ_FLAG | FUNC_READ_APP:
        raise ValueError(f"expected read response function 0xFB, got 0x{function:02X}")
    (status,) = struct.unpack_from("<B", frame, 13)
    if status != 0x00:
        raise ValueError(f"sensor reported error status 0x{status:02X}")
    data = bytes(frame[14:-1])
    (start,) = struct.unpack_from("<I", frame, 7)
    return device, start, data


def decode_resultant(data: bytes) -> tuple[float, float, float]:
    """Resultant force (Fx, Fy, Fz) in N from registers 1008-1010.

    Fx/Fy are signed, Fz unsigned; one LSB equals 0.1 N (manual 5.6.2).
    """
    if len(data) < 3:
        raise ValueError("resultant force needs 3 bytes")
    fx = data[0] - 256 if data[0] > 127 else data[0]
    fy = data[1] - 256 if data[1] > 127 else data[1]
    return (fx * 0.1, fy * 0.1, data[2] * 0.1)


def decode_distributed(data: bytes) -> tuple[tuple[float, float, float], ...]:
    """Per-point forces (Fx, Fy, Fz) in N from the register-1038 block.

    Three bytes per point (Fx signed, Fy signed, Fz unsigned), 1 LSB = 0.1 N.
    """
    if len(data) % 3 != 0:
        raise ValueError(f"distributed force needs a multiple of 3 bytes, got {len(data)}")
    points: list[tuple[float, float, float]] = []
    for i in range(0, len(data), 3):
        fx = data[i] - 256 if data[i] > 127 else data[i]
        fy = data[i + 1] - 256 if data[i + 1] > 127 else data[i + 1]
        points.append((fx * 0.1, fy * 0.1, data[i + 2] * 0.1))
    return tuple(points)


def build_force_poll(device: int, points: int) -> bytes:
    """Poll request for the distributed-force block of ``points`` points."""
    return build_read_request(device, ADDR_DISTRIBUTED_FORCE, points * 3)
