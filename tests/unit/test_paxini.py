"""PaXini GEN3 UART codec tests: manual golden examples, frames, decoding."""

import pytest

from tacstack.adapters.real_sensor import (
    build_force_poll,
    build_read_request,
    decode_distributed,
    decode_resultant,
    lrc,
    parse_response,
)

# The manual's three worked read-request examples (section 5.4.3), verbatim:
# read 32 bytes of 分布力 from start address 1038, device addresses 01/02/03.
MANUAL_REQUESTS = (
    bytes.fromhex("55AA09000100FB0E040000200 0CA".replace(" ", "")),
    bytes.fromhex("55AA09000200FB0E040000200 0C9".replace(" ", "")),
    bytes.fromhex("55AA09000300FB0E040000200 0C8".replace(" ", "")),
)


def test_manual_golden_requests_reproduced_exactly() -> None:
    for device, expected in enumerate(MANUAL_REQUESTS, start=1):
        assert build_read_request(device, 1038, 32) == expected


def test_lrc_is_twos_complement_of_byte_sum() -> None:
    frame = build_read_request(1, 1038, 32)
    assert lrc(frame[:-1]) == frame[-1]
    assert (sum(frame) & 0xFF) == 0


def test_build_read_request_validation() -> None:
    with pytest.raises(ValueError, match="device"):
        build_read_request(256, 1038, 3)
    with pytest.raises(ValueError, match="length must be positive"):
        build_read_request(1, 1038, 0)


def _response(device: int, start: int, data: bytes, *, status: int = 0) -> bytes:
    body = bytes([device, 0x00, 0x80 | 0x7B])
    body += start.to_bytes(4, byteorder="little")
    body += len(data).to_bytes(2, byteorder="little")
    body += bytes([status]) + data
    frame = b"\xaa\x55" + len(body).to_bytes(2, byteorder="little") + body
    return frame + bytes([lrc(frame)])


def test_parse_response_round_trip() -> None:
    request = build_read_request(1, 1038, 6)
    response = _response(1, 1038, b"\x01\xfe\x05\x00\x00\x0a")
    device, start, data = parse_response(response)
    assert device == 1 and start == 1038
    assert data == b"\x01\xfe\x05\x00\x00\x0a"
    # request and response headers differ by design (55 AA vs AA 55)
    assert request[:2] == b"\x55\xaa" and response[:2] == b"\xaa\x55"


def test_parse_response_rejects_corruption() -> None:
    good = _response(1, 1038, b"\x01\x02\x03")
    broken = bytearray(good)
    broken[-1] ^= 0xFF
    with pytest.raises(ValueError, match="LRC"):
        parse_response(bytes(broken))
    broken2 = bytearray(good)
    broken2[13] = 0x05  # nonzero status
    broken2[-1] = lrc(broken2[:-1])  # keep the LRC valid to isolate the status check
    with pytest.raises(ValueError, match="status"):
        parse_response(bytes(broken2))


def test_decode_resultant_signed_axes_and_scale() -> None:
    # Fx=0xFF wraps to -1 (-0.1 N), Fz=10 -> 1.0 N (manual 5.6.2: 1 LSB = 0.1 N)
    assert decode_resultant(bytes([0xFF, 0x02, 10])) == pytest.approx((-0.1, 0.2, 1.0))


def test_decode_distributed_splits_points() -> None:
    points = decode_distributed(bytes([0x00, 0x00, 25, 0x81, 0x00, 5]))
    assert points[0] == pytest.approx((0.0, 0.0, 2.5))
    assert points[1] == pytest.approx((-12.7, 0.0, 0.5))
    with pytest.raises(ValueError, match="multiple of 3"):
        decode_distributed(b"\x01\x02")


def test_build_force_poll_shape() -> None:
    # DP-S1813-Elite has 31 points: 93 data bytes requested
    frame = build_force_poll(1, 31)
    assert frame[6] == 0xFB
    assert frame[11:13] == (31 * 3).to_bytes(2, byteorder="little")
