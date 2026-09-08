"""PaXini PX6D six-axis F/T sensor USB / RS485 protocol codec.

Frame format (manual pages 09-10, shared by USB and RS485; CAN/CANFD carry
the same command set over different framing):

- command frame: ``AA 55`` <device_id> <cmd> [data] <crc8>
- CRC8 over cmd + data: standard CRC-8, polynomial 0x07, init 0x00, no
  reflection, final XOR 0xBC. The parameters are not stated in the manual;
  they were recovered by brute force from the manual's seven worked command
  examples and are pinned by tests.
- commands: 0x01 set id, 0x02 set auto-report rate (data = rate/4, 4-1000
  Hz), 0x03 start auto-stream, 0x04 stop, 0x05 get one frame, 0x07 get
  version, 0x10 calibrate (zero)
- one-frame response: 28 bytes = ``AA 55`` <id> <0x03> + 24 bytes = six
  axes x float32 LE (Fx, Fy, Fz, Mx, My, Mz) + CRC8

Known gap: the RESPONSE-frame CRC byte does not match any standard CRC8
parameter set (exhaustively searched windows/polynomial/init/xor), nor
CRC16 or additive rules. Response parsing therefore validates header,
length and address echo but does not enforce the CRC byte; flip
``parse_response(..., verify_crc=True)`` once the rule is confirmed
against captured hardware traffic (Phase 5).
"""

import struct
from dataclasses import dataclass

_HEADER = b"\xaa\x55"
_DEFAULT_DEVICE_ID = 0x7F

CMD_SET_ID = 0x01
CMD_SET_REPORT_RATE = 0x02
CMD_START_AUTO_STREAM = 0x03
CMD_STOP_AUTO_STREAM = 0x04
CMD_GET_FRAME = 0x05
CMD_GET_VERSION = 0x07
CMD_CALIBRATE = 0x10

_WRENCH_BYTES = 24


def crc8(data: bytes) -> int:
    """Vendor CRC8 over cmd + data (poly 0x07, init 0x00, xor 0xBC).

    The window is cmd + data only - the header and device id are excluded
    (verified against all seven manual command examples).
    """
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ 0xBC


def build_command(device_id: int, cmd: int, data: bytes = b"") -> bytes:
    """One command frame: ``AA 55`` <id> <cmd> [data] <crc8(cmd + data)>."""
    if not 0 <= device_id <= 255:
        raise ValueError("device_id must fit in one byte")
    body = bytes([device_id, cmd]) + data
    return _HEADER + body + bytes([crc8(bytes([cmd]) + data)])


def build_set_id(device_id: int, new_id: int) -> bytes:
    """Set a new device id; takes effect after power cycle (manual 5.2.2)."""
    if not 0 <= new_id <= 255:
        raise ValueError("new_id must fit in one byte")
    return build_command(device_id, CMD_SET_ID, bytes([new_id]))


def build_set_report_rate(device_id: int, rate_hz: int) -> bytes:
    """Set the auto-report rate; data = rate/4 (manual examples: 4Hz -> 0x01,
    100Hz -> 0x19)."""
    if not 4 <= rate_hz <= 1000:
        raise ValueError("rate_hz must be within 4..1000 Hz")
    return build_command(device_id, CMD_SET_REPORT_RATE, bytes([rate_hz // 4]))


def build_start_auto_stream(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Start 1 kHz continuous auto-reporting (USB config byte 0x04)."""
    return build_command(device_id, CMD_START_AUTO_STREAM, b"\x04")


def build_stop_auto_stream(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Stop continuous auto-reporting (USB config byte 0x00)."""
    return build_command(device_id, CMD_STOP_AUTO_STREAM, b"\x00")


def build_get_frame(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Request one six-axis wrench frame (USB config byte 0x01)."""
    return build_command(device_id, CMD_GET_FRAME, b"\x01")


def build_get_version(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Request the firmware version string (USB config byte 0x01)."""
    return build_command(device_id, CMD_GET_VERSION, b"\x01")


def build_calibrate(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Zero (tare) the sensor; run with the sensor unloaded (config 0x01)."""
    return build_command(device_id, CMD_CALIBRATE, b"\x01")


@dataclass(frozen=True)
class PX6DResponse:
    """One decoded response frame; CRC is exposed but lenient (see module notes)."""

    device_id: int
    cmd: int
    data: bytes
    crc: int


def parse_response(frame: bytes, *, verify_crc: bool = False) -> PX6DResponse:
    """Parse one response frame.

    Header, length and address echo are always enforced. ``verify_crc``
    stays False by default: the vendor response CRC rule does not match any
    standard CRC8 parameter set (exhaustively searched) and is pending
    confirmation against captured hardware traffic.
    """
    if len(frame) < 6:
        raise ValueError(f"response must be at least 6 bytes, got {len(frame)}")
    if frame[:2] != _HEADER:
        raise ValueError("response header must be AA 55")
    device_id, cmd = frame[2], frame[3]
    if verify_crc and crc8(bytes([cmd]) + frame[4:-1]) != frame[-1]:
        raise ValueError("response CRC mismatch")
    return PX6DResponse(device_id=device_id, cmd=cmd, data=bytes(frame[4:-1]), crc=frame[-1])


def decode_wrench(data: bytes) -> tuple[float, ...]:
    """Decode a data frame to (Fx, Fy, Fz, Mx, My, Mz), six float32 LE values."""
    if len(data) != _WRENCH_BYTES:
        raise ValueError(f"wrench frame must be {_WRENCH_BYTES} bytes, got {len(data)}")
    return struct.unpack("<6f", data)


def decode_version(data: bytes) -> str:
    """Version string: 0x00-padded ASCII, e.g. ``00 76 30 2E ... 00`` -> "v0.1.1"."""
    return bytes(data).strip(b"\x00").decode("ascii")
