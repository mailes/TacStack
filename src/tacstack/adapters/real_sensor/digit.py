"""Meta DIGIT vision-based tactile sensor: identity, mapping and semantics.

DIGIT is a UVC camera behind an illuminated gel, not a serial protocol, so
unlike the other modules in this package there are no byte frames to parse.
The hardware-free layer covers the three things that do not need the device:

- identity: USB IDs (VID 0x2833 / PID 0x0209, pinned by the official SDK's
  ``udev/50-DIGIT.rules``) and the udev property mapping the official
  digit-interface SDK enumerates with (``video4linux`` devices whose
  ``ID_MODEL`` is ``DIGIT``, serial from ``ID_SERIAL_SHORT``, capture path
  from ``DEVNAME``).
- stream facts: QVGA 320x240 at 60 fps (SDK default) and VGA 640x480 at
  30 fps; LED intensity spans 0-15.
- semantics: raw UVC frame -> validated ``TactileObservation`` (modality
  ``vision_tactile``, payload ``tactile_image``), plus a reference-frame
  tracker that derives contact and slip events from image differences --
  the signal the generic activity-based baselines cannot see in a raw RGB
  gel image.

The event emission reuses the exact hysteresis machines from the builtin
contact / slip models so DIGIT-derived events follow the same sequence
rules as runtime-scored ones. These trackers are adapter-level semantics,
not runtime models: a learned DIGIT model plugs into the Runtime instead.

Known gaps until hardware is captured (Phase 5): the live OpenCV capture
adapter; frame orientation (the SDK's ``get_frame`` transposes and flips
the sensor raster, so callers must feed one orientation consistently,
reference included); fisheye and per-device LED calibration; MJPEG vs YUYV
pixel-format negotiation. Where the MIT-licensed digit-interface SDK and
this module overlap, behavior follows the SDK; no SDK code is copied.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import exp, hypot, isfinite
from time import perf_counter
from typing import Any

import numpy as np
import numpy.typing as npt

from tacstack.core import EventKind, SensorDescriptor, TactileEvent, TactileObservation
from tacstack.models.contact.baseline import ContactHysteresis
from tacstack.models.slip.baseline import SlipEdgeTracker

DIGIT_MODEL = "DIGIT"
USB_VID = 0x2833
USB_PID = 0x0209

#: Default vendor for descriptors when udev provides no ``ID_VENDOR``.
_DEFAULT_VENDOR = "Meta"


@dataclass(frozen=True)
class DigitStream:
    """One UVC stream configuration (resolution and frame rate)."""

    width: int
    height: int
    fps: int


#: SDK default stream (digit.py: "Setting stream defaults to QVGA, 60fps").
QVGA = DigitStream(width=320, height=240, fps=60)
#: The SDK's alternative stream.
VGA = DigitStream(width=640, height=480, fps=30)
DEFAULT_STREAM = QVGA


@dataclass(frozen=True)
class DigitIdentity:
    """One DIGIT device as identified on the host.

    ``path`` is the udev ``DEVNAME`` (e.g. ``/dev/video2``) -- on Linux it is
    the capture handle OpenCV opens; other platforms supply their own handle
    in the Phase 5 live layer.
    """

    serial: str
    vendor: str | None = None
    revision: int | None = None
    path: str | None = None

    @property
    def sensor_id(self) -> str:
        return f"digit:{self.serial}"


def is_digit_usb_ids(vid: int, pid: int) -> bool:
    """Match the USB IDs pinned by the SDK's udev rule (0x2833 / 0x0209)."""
    return vid == USB_VID and pid == USB_PID


def parse_udev_device(properties: Mapping[str, str]) -> DigitIdentity | None:
    """Map one udev property mapping to a DIGIT identity, or None.

    Mirrors the official SDK's enumeration fields: requires ``ID_MODEL ==
    "DIGIT"`` and a non-empty ``ID_SERIAL_SHORT``; ``ID_REVISION`` is cast
    to int leniently (the SDK would raise on garbage there). Returning None
    for foreign devices lets callers filter a whole enumeration with one
    comprehension.
    """
    if properties.get("ID_MODEL") != DIGIT_MODEL:
        return None
    serial = properties.get("ID_SERIAL_SHORT", "").strip()
    if not serial:
        return None
    revision: int | None = None
    raw_revision = properties.get("ID_REVISION")
    if raw_revision:
        try:
            revision = int(raw_revision)
        except ValueError:
            revision = None
    return DigitIdentity(
        serial=serial,
        vendor=properties.get("ID_VENDOR") or None,
        revision=revision,
        path=properties.get("DEVNAME") or None,
    )


def frame_to_observation(
    frame: npt.NDArray[np.uint8],
    *,
    identity: DigitIdentity,
    timestamp_ns: int,
    stream: DigitStream = DEFAULT_STREAM,
) -> TactileObservation:
    """Validate one UVC frame and wrap it in a raw-first observation.

    The frame must be ``uint8`` HxWx3 at the stream's resolution. Callers
    pick the orientation; keep it consistent with the reference frame used
    for tracking. ``raw`` and ``tactile_image`` reference the same array,
    mirroring the OXT adapter's image-stream handling. Timestamps are
    stamped by the capture loop (``time.monotonic_ns()`` at frame arrival);
    the sensor carries no clock of its own.
    """
    expected = (stream.height, stream.width, 3)
    if frame.dtype != np.uint8:
        raise ValueError(f"frame dtype must be uint8, got {frame.dtype}")
    if frame.shape != expected:
        raise ValueError(
            f"frame shape must be {expected} for {stream.width}x{stream.height} @ "
            f"{stream.fps}fps, got {frame.shape}"
        )
    descriptor = SensorDescriptor(
        sensor_id=identity.sensor_id,
        vendor=identity.vendor or _DEFAULT_VENDOR,
        model=DIGIT_MODEL,
        modality="vision_tactile",
        frame_id=identity.serial,
        sample_rate_hz=float(stream.fps),
        capabilities=frozenset({"tactile_image"}),
    )
    metadata: dict[str, Any] = {
        "digit_stream": f"{stream.width}x{stream.height}@{stream.fps}",
    }
    if identity.revision is not None:
        metadata["digit_revision"] = identity.revision
    return TactileObservation(
        timestamp_ns=timestamp_ns,
        sensor=descriptor,
        raw=frame,
        tactile_image=frame,
        metadata=metadata,
    )


def contact_mask(
    frame: npt.NDArray[Any],
    reference: npt.NDArray[Any],
    *,
    diff_threshold: float = 0.08,
) -> npt.NDArray[np.float64]:
    """Soft per-pixel contact indicator in [0, 1] from the reference change.

    A pixel's mean absolute per-channel change (on the [0, 1] brightness
    scale) starts counting at ``diff_threshold`` and saturates at twice
    that value; anything below counts as background. Defaults are
    uncalibrated; per-device LED drift is the main threshold driver.
    """
    if not isfinite(diff_threshold) or diff_threshold <= 0:
        raise ValueError("diff_threshold must be finite and positive")
    current = np.asarray(frame, dtype=np.float64) / 255.0
    background = np.asarray(reference, dtype=np.float64) / 255.0
    if current.shape != background.shape:
        raise ValueError(
            f"frame shape {current.shape} does not match reference shape {background.shape}"
        )
    change = np.abs(current - background).mean(axis=-1)
    return np.clip((change - diff_threshold) / diff_threshold, 0.0, 1.0)


def mask_centroid(mask: npt.NDArray[np.float64]) -> tuple[float, float] | None:
    """Intensity-weighted centroid ``(x, y)``; None for an empty mask."""
    total = float(mask.sum())
    if total <= 0.0:
        return None
    ys, xs = np.indices(mask.shape)
    return (
        float((mask * xs).sum() / total),
        float((mask * ys).sum() / total),
    )


def _validate_frame(frame: npt.NDArray[Any]) -> npt.NDArray[Any]:
    array = np.asarray(frame)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[-1] != 3:
        raise ValueError(
            f"expected a uint8 HxWx3 image, got dtype={array.dtype} shape={array.shape}"
        )
    return array


class DigitFrameTracker:
    """Owns the reference (background) frame for one DIGIT device.

    With ``reference=None`` the first frame fed becomes the reference and
    yields an empty mask, so a live user needs no separate background shot;
    recorded episodes should pass the first frame explicitly for
    determinism. The state lives here so both derived trackers share one
    background. ``reset()`` re-captures after LED or temperature drift.
    """

    def __init__(
        self,
        *,
        reference: npt.NDArray[np.uint8] | None = None,
        diff_threshold: float = 0.08,
    ) -> None:
        self._reference = _validate_frame(reference) if reference is not None else None
        self._diff_threshold = diff_threshold

    @property
    def has_reference(self) -> bool:
        return self._reference is not None

    def reset(self, reference: npt.NDArray[np.uint8] | None = None) -> None:
        """Drop the stored background; the next frame re-captures unless given."""
        self._reference = _validate_frame(reference) if reference is not None else None

    def mask(self, frame: npt.NDArray[Any]) -> npt.NDArray[np.float64]:
        array = _validate_frame(frame)
        if self._reference is None:
            # Snapshot so a caller reusing its capture buffer cannot move the background.
            self._reference = np.array(array, copy=True)
            return np.zeros(array.shape[:2], dtype=np.float64)
        return contact_mask(array, self._reference, diff_threshold=self._diff_threshold)


class DigitContactTracker:
    """Reference-difference contact semantics: mask fraction -> logistic -> hysteresis.

    Emits edge-triggered ``contact_begin`` / ``contact_end`` events with
    ``model_id`` "digit-contact" by default; thresholds are uncalibrated.
    One instance tracks one device stream: hysteresis state lives here.
    """

    def __init__(
        self,
        frames: DigitFrameTracker,
        *,
        on_threshold: float = 0.6,
        off_threshold: float = 0.4,
        center: float = 0.02,
        gain: float = 40.0,
        model_id: str = "digit-contact",
    ) -> None:
        if not 0 < off_threshold < on_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 < off_threshold < on_threshold <= 1; "
                f"got off={off_threshold}, on={on_threshold}"
            )
        if not isfinite(center):
            raise ValueError("center must be finite")
        if not isfinite(gain) or gain <= 0:
            raise ValueError("gain must be finite and positive")
        self._frames = frames
        self._center = center
        self._gain = gain
        self._model_id = model_id
        self._hysteresis = ContactHysteresis(on_threshold=on_threshold, off_threshold=off_threshold)

    def infer(self, observation: TactileObservation) -> list[TactileEvent]:
        """Score one observation and return transition events (possibly none)."""
        started = perf_counter()
        fraction = self._contact_fraction(observation)
        probability = 1.0 / (1.0 + exp(-self._gain * (fraction - self._center)))
        kind: EventKind | None = self._hysteresis.update(probability)
        if kind is None:
            return []
        return [
            TactileEvent(
                timestamp_ns=observation.timestamp_ns,
                sensor_id=observation.sensor.sensor_id,
                kind=kind,
                probability=probability,
                model_id=self._model_id,
                latency_ms=(perf_counter() - started) * 1000.0,
                region=None,
                metadata={"contact_fraction": fraction},
            )
        ]

    def _contact_fraction(self, observation: TactileObservation) -> float:
        if observation.tactile_image is None:
            raise ValueError(
                "observation carries no tactile_image; DIGIT tracking needs image frames"
            )
        mask = self._frames.mask(np.asarray(observation.tactile_image))
        return float(mask.mean())


class DigitSlipTracker:
    """Centroid-displacement slip semantics over the shared reference mask.

    The signal is the Euclidean shift of the contact-mask centroid between
    consecutive frames, normalized by the image diagonal (1.0 spans the full
    frame), mapped through a logistic and emitted as rising-edge
    ``micro_slip`` / ``slip`` via the builtin edge tracker. Frames whose
    contact fraction falls below ``min_fraction`` carry no usable centroid,
    so they are silent and reset the previous position; thresholds are
    uncalibrated.
    """

    def __init__(
        self,
        frames: DigitFrameTracker,
        *,
        micro_threshold: float = 0.4,
        slip_threshold: float = 0.7,
        center: float = 0.01,
        gain: float = 80.0,
        min_fraction: float = 0.005,
        model_id: str = "digit-slip",
    ) -> None:
        if not 0 < micro_threshold < slip_threshold <= 1:
            raise ValueError(
                "thresholds must satisfy 0 < micro_threshold < slip_threshold <= 1; "
                f"got micro={micro_threshold}, slip={slip_threshold}"
            )
        if not isfinite(center):
            raise ValueError("center must be finite")
        if not isfinite(gain) or gain <= 0:
            raise ValueError("gain must be finite and positive")
        if not 0 < min_fraction < 1:
            raise ValueError("min_fraction must be in (0, 1)")
        self._frames = frames
        self._center = center
        self._gain = gain
        self._min_fraction = min_fraction
        self._model_id = model_id
        self._tracker = SlipEdgeTracker(
            micro_threshold=micro_threshold, slip_threshold=slip_threshold
        )
        self._previous: tuple[float, float] | None = None

    def infer(self, observation: TactileObservation) -> list[TactileEvent]:
        """Compare against the previous frame and return rising-edge events."""
        started = perf_counter()
        if observation.tactile_image is None:
            raise ValueError(
                "observation carries no tactile_image; DIGIT tracking needs image frames"
            )
        array = np.asarray(observation.tactile_image)
        mask = self._frames.mask(array)
        fraction = float(mask.mean())
        if fraction < self._min_fraction:
            self._previous = None
            return []
        centroid = mask_centroid(mask)
        if centroid is None:  # unreachable: fraction > 0 implies a non-empty mask
            return []
        displacement = self._displacement(centroid, array.shape)
        self._previous = centroid
        probability = 1.0 / (1.0 + exp(-self._gain * (displacement - self._center)))
        kind: EventKind | None = self._tracker.update(probability)
        if kind is None:
            return []
        return [
            TactileEvent(
                timestamp_ns=observation.timestamp_ns,
                sensor_id=observation.sensor.sensor_id,
                kind=kind,
                probability=probability,
                model_id=self._model_id,
                latency_ms=(perf_counter() - started) * 1000.0,
                region=None,
                metadata={"centroid_shift": displacement, "contact_fraction": fraction},
            )
        ]

    def _displacement(self, centroid: tuple[float, float], shape: tuple[int, ...]) -> float:
        if self._previous is None:
            return 0.0
        shift = hypot(centroid[0] - self._previous[0], centroid[1] - self._previous[1])
        diagonal = hypot(shape[0], shape[1])
        return shift / diagonal
