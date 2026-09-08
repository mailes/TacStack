"""PaXini PX3Q joint torque sensor USB / RS485 protocol codec.

The PX3Q measures three-axis joint torque (Mx, My, Mz) as float32 and ships
configured for exactly one of RS485 / USB / CAN / EtherCAT (manual section 1.1).
USB and RS485 share byte-identical framing (manual 5.1 / 5.2): 921600 8N1, no
parity, no flow control. CAN uses a different envelope (manual 5.3,
0x200/0x180/0x280/0x380 + device id) and is not implemented here - the
procurement decision is USB-first; CAN helpers can follow the same pattern if a
CAN unit ever arrives.

Frame rules (manual 5.1.2 / 5.2.1, default device id 0x7F):
- command:  ``AA 55`` <device_id> <cmd> <1 data byte> <crc8>
- response: ``AA 55`` <device_id> <cmd> <M data bytes> <crc8> where M = 12 for
  torque frames (cmd 0x03) and M = 8 for the other read commands; set-report-
  rate answers by echoing the request frame verbatim
- commands: 0x01 set id (power cycle to apply), 0x02 set auto-report rate
  (data = rate/4, manual examples 4 Hz -> 0x01, 100 Hz -> 0x19, auto-report
  example runs 1 kHz), 0x03 start auto-stream (data 0x04), 0x04 stop (0x00),
  0x05 get one frame (0x01), 0x07 get version (0x01), 0x10 calibrate/zero
  (0x01)
- torque frame payload: Mx, My, Mz as three float32 little-endian, N*m (the
  spec table rates models PX3Q-50/60/70 at 30/50/100 N*m full scale)
- version payload: 8 bytes, first and last fixed 0x00, the middle six are the
  ASCII version, e.g. ``00 76 30 2E 31 2E 31 00`` -> "v0.1.1"
- CRC8 over cmd + data (header and device id excluded): poly 0x07, init 0x00,
  no reflection, final XOR 0xBC - the same vendor rule as PX6D, verified
  against all eight manual request examples

Known gap: the RESPONSE-frame CRC byte matches the request rule only for the
verbatim rate echoes; for torque/version/ack frames no standard CRC8 parameter
set explains it (exhaustively searched windows/poly/init/xor including
reflected variants, same outcome as PX6D). Response parsing therefore
validates header, length and address echo but does not enforce the CRC byte;
flip ``parse_response(..., verify_crc=True)`` once captured hardware traffic
confirms the rule (Phase 5).
"""

import struct
from dataclasses import dataclass

_HEADER = b"\xaa\x55"
_DEFAULT_DEVICE_ID = 0x7F

SERIAL_BAUDRATE = 921600  # 8N1, no parity, no flow control (manual 5.1.1)

CMD_SET_ID = 0x01
CMD_SET_REPORT_RATE = 0x02
CMD_START_AUTO_STREAM = 0x03
CMD_STOP_AUTO_STREAM = 0x04
CMD_GET_FRAME = 0x05
CMD_GET_VERSION = 0x07
CMD_CALIBRATE = 0x10

_TORQUE_BYTES = 12


def crc8(data: bytes) -> int:
    """Vendor CRC8 over cmd + data (poly 0x07, init 0x00, xor 0xBC).

    Same parameters as the PX6D; the window is cmd + data only - header and
    device id are excluded (verified against all eight manual examples).
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
    """Set a new device id; takes effect after a power cycle (manual 5.3.2)."""
    if not 0 <= new_id <= 255:
        raise ValueError("new_id must fit in one byte")
    return build_command(device_id, CMD_SET_ID, bytes([new_id]))


def build_set_report_rate(device_id: int, rate_hz: int) -> bytes:
    """Set the auto-report rate; data = rate/4 (manual examples: 4 Hz -> 0x01,
    100 Hz -> 0x19; the worked auto-report example runs 1 kHz)."""
    if not 4 <= rate_hz <= 1000:
        raise ValueError("rate_hz must be within 4..1000 Hz")
    return build_command(device_id, CMD_SET_REPORT_RATE, bytes([rate_hz // 4]))


def build_start_auto_stream(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Start continuous auto-reporting at the configured rate (USB/RS485
    config byte 0x04; the manual's worked example is 1 kHz)."""
    return build_command(device_id, CMD_START_AUTO_STREAM, b"\x04")


def build_stop_auto_stream(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Stop continuous auto-reporting (config byte 0x00)."""
    return build_command(device_id, CMD_STOP_AUTO_STREAM, b"\x00")


def build_get_frame(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Request one three-axis torque frame (config byte 0x01)."""
    return build_command(device_id, CMD_GET_FRAME, b"\x01")


def build_get_version(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Request the firmware version string (config byte 0x01)."""
    return build_command(device_id, CMD_GET_VERSION, b"\x01")


def build_calibrate(device_id: int = _DEFAULT_DEVICE_ID) -> bytes:
    """Zero (tare) the sensor; run with the joint unloaded (config 0x01)."""
    return build_command(device_id, CMD_CALIBRATE, b"\x01")


@dataclass(frozen=True)
class PX3QResponse:
    """One decoded response frame; CRC is exposed but lenient (see module notes)."""

    device_id: int
    cmd: int
    data: bytes
    crc: int


def parse_response(frame: bytes, *, verify_crc: bool = False) -> PX3QResponse:
    """Parse one response frame.

    Header, length and address echo are always enforced. ``verify_crc``
    stays False by default: the vendor response CRC rule does not match the
    request CRC8 for torque/version/ack frames (exhaustively searched) and is
    pending confirmation against captured hardware traffic.
    """
    if len(frame) < 6:
        raise ValueError(f"response must be at least 6 bytes, got {len(frame)}")
    if frame[:2] != _HEADER:
        raise ValueError("response header must be AA 55")
    device_id, cmd = frame[2], frame[3]
    if verify_crc and crc8(bytes([cmd]) + frame[4:-1]) != frame[-1]:
        raise ValueError("response CRC mismatch")
    return PX3QResponse(device_id=device_id, cmd=cmd, data=bytes(frame[4:-1]), crc=frame[-1])


def decode_torque(data: bytes) -> tuple[float, float, float]:
    """Decode a torque frame payload to (Mx, My, Mz) in N*m, float32 LE."""
    if len(data) != _TORQUE_BYTES:
        raise ValueError(f"torque frame must be {_TORQUE_BYTES} bytes, got {len(data)}")
    mx, my, mz = struct.unpack("<3f", data)
    return (mx, my, mz)


def decode_version(data: bytes) -> str:
    """Version string: 0x00-padded ASCII, e.g. ``00 76 30 2E ... 00`` -> "v0.1.1"."""
    return bytes(data).strip(b"\x00").decode("ascii")
