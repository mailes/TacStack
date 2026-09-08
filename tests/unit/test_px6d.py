"""PX6D protocol tests: manual golden frames, CRC8 recovery, wrench decode."""

import pytest

from tacstack.adapters.real_sensor.px6d import (
    build_calibrate,
    build_command,
    build_get_frame,
    build_get_version,
    build_set_id,
    build_set_report_rate,
    build_start_auto_stream,
    build_stop_auto_stream,
    crc8,
    decode_version,
    decode_wrench,
    parse_response,
)

# 手册 5.1.3 / 5.2.2 的全部发送样例（帧内容含 CRC）——CRC8 参数的反推依据
MANUAL_REQUESTS = {
    "set-id": ("AA557F0101AE", 0xAE),
    "set-rate-4hz": ("AA557F020191", 0x91),
    "start-1khz": ("AA557F03049F", 0x9F),
    "stop": ("AA557F0400E8", 0xE8),
    "get-frame": ("AA557F0501FA", 0xFA),
    "get-version": ("AA557F0701D0", 0xD0),
    "calibrate": ("AA557F1001EC", 0xEC),
}


def test_crc8_reproduces_every_manual_request() -> None:
    for name, (hexstr, expected) in MANUAL_REQUESTS.items():
        frame = bytes.fromhex(hexstr)
        # CRC window: cmd + data only (header and device id excluded)
        assert crc8(frame[3:-1]) == expected, f"{name} CRC mismatch"
        assert build_command(0x7F, frame[3], frame[4:-1]) == frame


def test_set_id_builder() -> None:
    # manual: AA 55 7F 01 01 AE (last byte is the CRC)
    assert build_set_id(0x7F, 0x01) == bytes.fromhex("AA557F0101AE")
    with pytest.raises(ValueError, match="new_id"):
        build_set_id(0x7F, 256)


def test_set_report_rate_builder() -> None:
    # manual: 4 Hz -> data 0x01; 100 Hz -> data 0x19 (rate/4)
    assert build_set_report_rate(0x7F, 4) == bytes.fromhex("AA557F020191")
    assert build_set_report_rate(0x7F, 100) == bytes.fromhex("AA557F0219D9")
    with pytest.raises(ValueError, match="4..1000"):
        build_set_report_rate(0x7F, 2)


def test_simple_builders() -> None:
    assert build_start_auto_stream() == bytes.fromhex("AA557F03049F")
    assert build_stop_auto_stream() == bytes.fromhex("AA557F0400E8")
    assert build_get_frame() == bytes.fromhex("AA557F0501FA")
    assert build_get_version() == bytes.fromhex("AA557F0701D0")
    assert build_calibrate() == bytes.fromhex("AA557F1001EC")


# 手册 5.2.2 序号 3 的获取一帧应答样例（28 字节，六轴 float32 LE + CRC）
MANUAL_FRAME_RESPONSE = bytes.fromhex("AA557F03310C0BBD5C7638BDFC35A23C6EE8B7BAE69C243936C89FB943")


def test_parse_response_data_frame() -> None:
    response = parse_response(MANUAL_FRAME_RESPONSE)
    assert response.device_id == 0x7F
    assert response.cmd == 0x03
    assert len(response.data) == 24
    wrench = decode_wrench(response.data)
    # a very light touch: Fz ≈ 0.02 N, tangential forces near zero
    assert wrench[0] == pytest.approx(-0.034, abs=1e-3)
    assert wrench[2] == pytest.approx(0.0198, abs=1e-3)


def test_parse_response_zero_payload() -> None:
    calibrate_ack = bytes.fromhex("AA557F1000000000000000E2")
    response = parse_response(calibrate_ack)
    assert response.device_id == 0x7F
    assert response.cmd == 0x10
    assert response.data == b"\x00" * 7


def test_parse_response_lenient_crc_by_default() -> None:
    broken = bytearray(MANUAL_FRAME_RESPONSE)
    broken[-1] ^= 0xFF  # response CRC rule is unidentified; must not raise
    response = parse_response(bytes(broken))
    assert response.cmd == 0x03
    with pytest.raises(ValueError, match="CRC"):
        parse_response(bytes(broken), verify_crc=True)


def test_parse_response_rejects_bad_header_and_length() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_response(b"\x55\xaa" + MANUAL_FRAME_RESPONSE[2:])
    with pytest.raises(ValueError, match="at least 6"):
        parse_response(b"\xaa\x55\x7f\x03\x00")


def test_decode_version_strips_padding() -> None:
    assert decode_version(bytes.fromhex("0076302E312E3100")) == "v0.1.1"
