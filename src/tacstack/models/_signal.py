"""Shared numeric signal extraction for the built-in baseline models."""

import numpy as np

from tacstack.core import TactileObservation


def tactile_array(observation: TactileObservation) -> np.ndarray:
    """Return the tactile payload as a float array; images normalized to [0, 1].

    Raises ValueError when the observation carries neither payload, so models
    fail loudly on streams that cannot satisfy them.
    """
    if observation.taxels is not None:
        return np.asarray(observation.taxels, dtype=np.float64)
    if observation.tactile_image is not None:
        image = np.asarray(observation.tactile_image)
        if image.dtype == np.uint8:
            return image.astype(np.float64) / 255.0
        return np.asarray(image, dtype=np.float64)
    raise ValueError(
        "observation carries no tactile payload (taxels and tactile_image are "
        f"both None); stream {observation.sensor.sensor_id!r} cannot feed this model"
    )


def magnitude_frame(array: np.ndarray) -> np.ndarray:
    """Collapse the trailing axis (axis-stacked payloads) to per-element magnitudes."""
    if array.ndim >= 4:
        return np.asarray(np.linalg.norm(array, axis=-1), dtype=np.float64)
    return np.abs(array)


def activity(observation: TactileObservation) -> float:
    """Scalar activity of one frame: mean magnitude of the tactile payload."""
    return float(magnitude_frame(tactile_array(observation)).mean())
