"""Live sensor adapters. Protocol codecs implemented: M0404S, PaXini GEN3,
PX6D six-axis F/T (USB) and PX3Q joint torque (USB/RS485); the Meta DIGIT
vision-tactile identity / semantics layer is implemented, its live OpenCV
capture lands with the hardware (Phase 5)."""

from tacstack.adapters.real_sensor.digit import (
    DEFAULT_STREAM,
    QVGA,
    VGA,
    DigitContactTracker,
    DigitFrameTracker,
    DigitIdentity,
    DigitSlipTracker,
    DigitStream,
    contact_mask,
    frame_to_observation,
    is_digit_usb_ids,
    mask_centroid,
    parse_udev_device,
)
from tacstack.adapters.real_sensor.m0404s import (
    M0404SFrame,
    M0404SStreamParser,
    checksum,
    parse_frame,
)
from tacstack.adapters.real_sensor.paxini import (
    build_force_poll,
    build_read_request,
    decode_distributed,
    decode_resultant,
    lrc,
    parse_response,
)

__all__ = [
    "DEFAULT_STREAM",
    "M0404SFrame",
    "M0404SStreamParser",
    "QVGA",
    "VGA",
    "DigitContactTracker",
    "DigitFrameTracker",
    "DigitIdentity",
    "DigitSlipTracker",
    "DigitStream",
    "build_force_poll",
    "build_read_request",
    "checksum",
    "contact_mask",
    "decode_distributed",
    "decode_resultant",
    "frame_to_observation",
    "is_digit_usb_ids",
    "lrc",
    "mask_centroid",
    "parse_frame",
    "parse_response",
    "parse_udev_device",
]
