"""PX3Q protocol tests: manual golden frames, CRC8 verification, torque decode."""

import pytest

from tacstack.adapters.real_sensor.px3q import (
    SERIAL_BAUDRATE,
    build_calibrate,
    build_command,
    build_get_frame,
    build_get_version,
    build_set_id,
    build_set_report_rate,
    build_start_auto_stream,
    build_stop_auto_stream,
    crc8,
    decode_torque,
    decode_version,
    parse_response,
)

# 手册 5.1.3 / 5.2.2 的全部发送样例（帧内容含 CRC）——USB 与 RS485 示例逐字节相同
MANUAL_REQUESTS = {
    "set-id": ("AA557F0101AE", 0xAE),
    "set-rate-4hz": ("AA557F020191", 0x91),
    "set-rate-100hz": ("AA557F0219D9", 0xD9),
    "start-1khz": ("AA557F03049F", 0x9F),
    "stop": ("AA557F0400E8", 0xE8),
    "get-frame": ("AA557F0501FA", 0xFA),
    "get-version": ("AA557F0701D0", 0xD0),
    "calibrate": ("AA557F1001EC", 0xEC),
}


def test_serial_baudrate_matches_manual() -> None:
    assert SERIAL_BAUDRATE == 921600


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


def test_build_command_rejects_bad_device_id() -> None:
    with pytest.raises(ValueError, match="device_id"):
        build_command(256, 0x05, b"\x01")


# 手册 5.2.2 序号 3/5 的应答样例（17 字节：cmd 03 + 三轴 float32 LE + CRC）
MANUAL_TORQUE_RESPONSE = bytes.fromhex("AA557F030B6A2C3DD8BCD03D643A7E3EC1")

# 手册 5.1.3 / 5.2.2 的其余应答样例（ack = cmd + 8 个 0x00 + CRC，共 13 字节；
# 设置频率的应答是请求帧原样回显）
MANUAL_ZERO_ACKS = {
    "set-id-ack": ("AA557F01" + "00" * 8 + "1E", 0x01),
    "stop-ack": ("AA557F04" + "00" * 8 + "84", 0x04),
    "calibrate-ack": ("AA557F10" + "00" * 8 + "E2", 0x10),
}


def test_parse_response_torque_frame() -> None:
    response = parse_response(MANUAL_TORQUE_RESPONSE)
    assert response.device_id == 0x7F
    assert response.cmd == 0x03
    assert len(response.data) == 12
    mx, my, mz = decode_torque(response.data)
    # manual sample frame decodes to a light static load, all axes well inside
    # the 30/50/100 N*m model ranges
    assert mx == pytest.approx(0.042093, abs=1e-6)
    assert my == pytest.approx(0.101923, abs=1e-6)
    assert mz == pytest.approx(0.248270, abs=1e-6)


def test_parse_response_zero_acks() -> None:
    for name, (hexstr, cmd) in MANUAL_ZERO_ACKS.items():
        frame = bytes.fromhex(hexstr)
        assert len(frame) == 13, name
        response = parse_response(frame)
        assert response.device_id == 0x7F, name
        assert response.cmd == cmd, name
        assert response.data == b"\x00" * 8, name


def test_parse_response_rate_echo() -> None:
    # set-report-rate answers by echoing the request frame verbatim
    for hexstr in ("AA557F020191", "AA557F0219D9"):
        response = parse_response(bytes.fromhex(hexstr))
        assert response.cmd == 0x02
        assert len(response.data) == 1


def test_parse_response_lenient_crc_by_default() -> None:
    broken = bytearray(MANUAL_TORQUE_RESPONSE)
    broken[-1] ^= 0xFF  # response CRC rule is unidentified; must not raise
    response = parse_response(bytes(broken))
    assert response.cmd == 0x03
    with pytest.raises(ValueError, match="CRC"):
        parse_response(bytes(broken), verify_crc=True)


def test_parse_response_rejects_bad_header_and_length() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_response(b"\x55\xaa" + MANUAL_TORQUE_RESPONSE[2:])
    with pytest.raises(ValueError, match="at least 6"):
        parse_response(b"\xaa\x55\x7f\x03\x00")


def test_decode_torque_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="12 bytes"):
        decode_torque(b"\x00" * 24)  # a PX6D-sized wrench payload is not torque


def test_decode_version_strips_padding() -> None:
    assert decode_version(bytes.fromhex("0076302E312E3100")) == "v0.1.1"
