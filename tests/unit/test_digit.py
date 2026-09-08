"""DIGIT semantics tests: SDK-pinned identity facts, observation mapping,
reference-difference contact / slip event sequences (synthetic frames only)."""

import numpy as np
import pytest

from tacstack.adapters.real_sensor import (
    QVGA,
    VGA,
    DigitContactTracker,
    DigitFrameTracker,
    DigitIdentity,
    DigitSlipTracker,
    contact_mask,
    frame_to_observation,
    is_digit_usb_ids,
    mask_centroid,
    parse_udev_device,
)
from tacstack.core import TactileObservation

HEIGHT, WIDTH = 240, 320

IDENTITY = DigitIdentity(serial="D205170070", vendor="Meta", revision=200, path="/dev/video2")

# udev fields the official SDK's _parse consumes, verbatim structure.
UDEV_DIGIT = {
    "SUBSYSTEM": "video4linux",
    "ID_MODEL": "DIGIT",
    "ID_VENDOR": "Meta",
    "ID_SERIAL_SHORT": "D205170070",
    "ID_REVISION": "0200",
    "DEVNAME": "/dev/video2",
}


def _background() -> np.ndarray:
    gradient = np.linspace(60.0, 120.0, WIDTH).astype(np.uint8)
    return np.stack([np.tile(gradient, (HEIGHT, 1))] * 3, axis=-1)


def _with_blob(frame: np.ndarray, cx: int = 160, cy: int = 120, radius: int = 30) -> np.ndarray:
    out = frame.copy()
    yy, xx = np.ogrid[:HEIGHT, :WIDTH]
    out[(xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2] = 230
    return out


def _observation(frame: np.ndarray, timestamp_ns: int) -> TactileObservation:
    return frame_to_observation(frame, identity=IDENTITY, timestamp_ns=timestamp_ns)


# --- identity facts pinned from the official digit-interface SDK ----------


def test_udev_golden_mapping() -> None:
    identity = parse_udev_device(UDEV_DIGIT)
    assert identity == IDENTITY
    assert identity is not None and identity.sensor_id == "digit:D205170070"


def test_udev_rejects_foreign_and_unserialised_devices() -> None:
    assert parse_udev_device({**UDEV_DIGIT, "ID_MODEL": "USB_Camera"}) is None
    assert parse_udev_device({"ID_MODEL": "DIGIT"}) is None
    assert parse_udev_device({**UDEV_DIGIT, "ID_SERIAL_SHORT": "  "}) is None


def test_udev_lenient_revision_cast() -> None:
    identity = parse_udev_device({**UDEV_DIGIT, "ID_REVISION": "garbage", "DEVNAME": ""})
    assert identity is not None
    assert identity.revision is None and identity.path is None


def test_usb_ids_match_udev_rule() -> None:
    assert is_digit_usb_ids(0x2833, 0x0209)
    assert not is_digit_usb_ids(0x2833, 0x020A)
    assert not is_digit_usb_ids(0x2834, 0x0209)


def test_stream_defaults_match_sdk() -> None:
    assert (QVGA.width, QVGA.height, QVGA.fps) == (320, 240, 60)
    assert (VGA.width, VGA.height, VGA.fps) == (640, 480, 30)


# --- observation mapping ---------------------------------------------------


def test_frame_to_observation_fields() -> None:
    frame = _background()
    observation = _observation(frame, timestamp_ns=42)
    assert observation.timestamp_ns == 42
    assert observation.raw is frame and observation.tactile_image is frame
    sensor = observation.sensor
    assert sensor.sensor_id == "digit:D205170070"
    assert sensor.vendor == "Meta"
    assert sensor.model == "DIGIT"
    assert sensor.modality == "vision_tactile"
    assert sensor.frame_id == "D205170070"
    assert sensor.sample_rate_hz == 60.0
    assert sensor.capabilities == frozenset({"tactile_image"})
    assert observation.metadata["digit_stream"] == "320x240@60"
    assert observation.metadata["digit_revision"] == 200


def test_frame_validation_rejects_wrong_shape_and_dtype() -> None:
    frame = _background()
    with pytest.raises(ValueError, match="dtype must be uint8"):
        frame_to_observation(frame.astype(np.float32), identity=IDENTITY, timestamp_ns=0)
    with pytest.raises(ValueError, match="frame shape must be"):
        frame_to_observation(frame[1:], identity=IDENTITY, timestamp_ns=0)
    with pytest.raises(ValueError, match="frame shape must be"):
        frame_to_observation(
            np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8), identity=IDENTITY, timestamp_ns=0
        )


def test_frame_validation_accepts_vga_stream() -> None:
    vga = np.zeros((480, 640, 3), dtype=np.uint8)
    observation = frame_to_observation(vga, identity=IDENTITY, timestamp_ns=0, stream=VGA)
    assert observation.metadata["digit_stream"] == "640x480@30"
    assert observation.sensor.sample_rate_hz == 30.0


# --- mask / centroid primitives ---------------------------------------------


def test_contact_mask_saturates_on_synthetic_blob() -> None:
    background = _background()
    mask = contact_mask(_with_blob(background), background)
    assert mask.shape == (HEIGHT, WIDTH)
    assert mask[120, 160] == pytest.approx(1.0)  # blob centre: full contact
    assert mask[10, 10] == pytest.approx(0.0)  # untouched background
    with pytest.raises(ValueError, match="does not match reference shape"):
        contact_mask(_with_blob(background), background[1:])
    with pytest.raises(ValueError, match="diff_threshold must be"):
        contact_mask(background, background, diff_threshold=0.0)


def test_mask_centroid_of_blob_and_empty_mask() -> None:
    background = _background()
    assert mask_centroid(np.zeros((HEIGHT, WIDTH))) is None
    centroid = mask_centroid(contact_mask(_with_blob(background), background))
    assert centroid is not None
    assert centroid == pytest.approx((160.0, 120.0))


# --- contact tracker ---------------------------------------------------------


def test_contact_tracker_emits_edge_triggered_sequence() -> None:
    background = _background()
    tracker = DigitContactTracker(DigitFrameTracker(reference=background))
    assert tracker.infer(_observation(background, 0)) == []
    begin = tracker.infer(_observation(_with_blob(background), 33_333_333))
    assert len(begin) == 1
    assert begin[0].kind == "contact_begin"
    assert begin[0].probability > 0.6
    assert begin[0].model_id == "digit-contact"
    assert begin[0].sensor_id == "digit:D205170070"
    assert begin[0].metadata["contact_fraction"] > 0.03
    assert tracker.infer(_observation(_with_blob(background), 66_666_666)) == []
    end = tracker.infer(_observation(background, 100_000_000))
    assert len(end) == 1 and end[0].kind == "contact_end" and end[0].probability < 0.4
    assert tracker.infer(_observation(background, 133_333_333)) == []


def test_contact_tracker_captures_reference_on_first_frame() -> None:
    background = _background()
    frames = DigitFrameTracker()
    assert not frames.has_reference
    tracker = DigitContactTracker(frames)
    assert tracker.infer(_observation(background, 0)) == []
    assert frames.has_reference
    assert tracker.infer(_observation(background, 33_333_333)) == []
    assert (
        tracker.infer(_observation(_with_blob(background), 66_666_666))[0].kind == "contact_begin"
    )


def test_contact_tracker_rejects_invalid_thresholds_and_payload() -> None:
    with pytest.raises(ValueError, match="thresholds must satisfy"):
        DigitContactTracker(DigitFrameTracker(), on_threshold=0.4, off_threshold=0.6)
    bare = TactileObservation(
        timestamp_ns=0, sensor=_observation(_background(), 0).sensor, raw=None
    )
    with pytest.raises(ValueError, match="no tactile_image"):
        DigitContactTracker(DigitFrameTracker()).infer(bare)


def test_frame_tracker_reset_recaptures_background() -> None:
    background = _background()
    frames = DigitFrameTracker(reference=background)
    frames.reset()
    assert not frames.has_reference
    shifted = _with_blob(background)
    assert frames.mask(shifted).sum() == 0.0  # captured as the new reference
    assert frames.mask(background).mean() > 0.0  # old background now reads as contact
    frames.reset(background)
    assert frames.mask(background).sum() == 0.0


def test_frame_tracker_snapshots_auto_captured_reference() -> None:
    background = _background()
    frames = DigitFrameTracker()
    frames.mask(background)
    background[:] = 255  # a caller reusing its capture buffer must not move the background
    assert frames.mask(background).mean() > 0.0


def test_slip_tracker_emits_rising_edge_sequence() -> None:
    background = _background()
    tracker = DigitSlipTracker(DigitFrameTracker(reference=background))
    assert tracker.infer(_observation(_with_blob(background, cx=100), 0)) == []
    slip = tracker.infer(_observation(_with_blob(background, cx=140), 33_333_333))
    assert len(slip) == 1
    assert slip[0].kind == "slip"
    assert slip[0].model_id == "digit-slip"
    assert slip[0].metadata["centroid_shift"] == pytest.approx(0.1, abs=0.01)
    assert tracker.infer(_observation(_with_blob(background, cx=140), 66_666_666)) == []
    micro = tracker.infer(_observation(_with_blob(background, cx=145), 100_000_000))
    assert len(micro) == 1 and micro[0].kind == "micro_slip"


def test_slip_tracker_silent_without_contact() -> None:
    background = _background()
    tracker = DigitSlipTracker(DigitFrameTracker(reference=background))
    assert tracker.infer(_observation(background, 0)) == []
    assert tracker.infer(_observation(background, 33_333_333)) == []


def test_slip_tracker_rejects_invalid_parameters_and_payload() -> None:
    frames = DigitFrameTracker(reference=_background())
    with pytest.raises(ValueError, match="thresholds must satisfy"):
        DigitSlipTracker(frames, micro_threshold=0.8, slip_threshold=0.4)
    with pytest.raises(ValueError, match="min_fraction must be"):
        DigitSlipTracker(frames, min_fraction=0.0)
    bare = TactileObservation(
        timestamp_ns=0, sensor=_observation(_background(), 0).sensor, raw=None
    )
    with pytest.raises(ValueError, match="no tactile_image"):
        DigitSlipTracker(frames).infer(bare)
