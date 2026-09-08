"""M0404S protocol parser tests: manual golden frame, validation, stream resync."""

import pytest

from tacstack.adapters.real_sensor import (
    M0404SStreamParser,
    checksum,
    parse_frame,
)

# The vendor manual's worked example frame (section 3.4), verbatim.
MANUAL_FRAME = bytes.fromhex(
    "AA 01 00 4E 00 11 01 06 00 00 01 6A 00 30 01 3F"
    "00 0E 00 00 02 BD 00 00 00 B2 00 37 00 AF 01 E2 00 08 3C".replace(" ", "")
)

MANUAL_POINTS = (
    78,
    17,
    262,
    0,
    362,
    48,
    319,
    14,
    0,
    701,
    0,
    178,
    55,
    175,
    482,
    8,
)


def test_manual_golden_frame_decodes_exactly() -> None:
    frame = parse_frame(MANUAL_FRAME)
    assert frame.packet == 1
    assert frame.points == MANUAL_POINTS
    assert len(frame.points) == 16


def test_checksum_matches_manual_low_byte() -> None:
    assert checksum(MANUAL_FRAME[:34]) == 0x3C
    assert checksum(MANUAL_FRAME[:34]) == MANUAL_FRAME[34]


def test_wrong_length_rejected() -> None:
    with pytest.raises(ValueError, match="35 bytes"):
        parse_frame(MANUAL_FRAME[:-1])
    with pytest.raises(ValueError, match="35 bytes"):
        parse_frame(MANUAL_FRAME + b"\x00")


def test_wrong_header_rejected() -> None:
    broken = bytes([0xAB]) + MANUAL_FRAME[1:]
    with pytest.raises(ValueError, match="header"):
        parse_frame(broken)


def test_checksum_mismatch_rejected() -> None:
    broken = bytearray(MANUAL_FRAME)
    broken[20] ^= 0xFF  # corrupt a data byte, keep the trailer
    with pytest.raises(ValueError, match="checksum"):
        parse_frame(bytes(broken))


def _make_frame(packet: int, points: tuple[int, ...]) -> bytes:
    body = bytearray([0xAA, packet & 0xFF])
    for value in points:
        body += int(value).to_bytes(2, byteorder="big")
    body.append(checksum(bytes(body)))
    return bytes(body)


def test_stream_parser_splits_back_to_back_frames() -> None:
    parser = M0404SStreamParser()
    second = _make_frame(2, tuple(range(16)))
    frames = parser.feed(MANUAL_FRAME + second)
    assert [f.packet for f in frames] == [1, 2]
    assert frames[0].points == MANUAL_POINTS
    assert frames[1].points == tuple(range(16))
    assert parser.frames_ok == 2 and parser.frames_bad == 0


def test_stream_parser_resyncs_after_garbage() -> None:
    parser = M0404SStreamParser()
    frames = parser.feed(b"\x00\x13\x37garbage" + MANUAL_FRAME + b"\xff\x00")
    assert [f.packet for f in frames] == [1]
    assert parser.frames_ok == 1 and parser.frames_bad >= 1


def test_stream_parser_survives_corrupted_frame() -> None:
    parser = M0404SStreamParser()
    corrupted = bytearray(MANUAL_FRAME)
    corrupted[10] ^= 0x55
    second = _make_frame(2, tuple(range(16)))
    frames = parser.feed(bytes(corrupted) + second)
    assert [f.packet for f in frames] == [2]
    assert parser.frames_bad >= 1


def test_stream_parser_handles_partial_feed() -> None:
    parser = M0404SStreamParser()
    assert parser.feed(MANUAL_FRAME[:10]) == []
    frames = parser.feed(MANUAL_FRAME[10:])
    assert [f.packet for f in frames] == [1]


def test_packet_counter_wraps_at_256() -> None:
    frame = parse_frame(_make_frame(256, tuple(range(16))))
    assert frame.packet == 0
