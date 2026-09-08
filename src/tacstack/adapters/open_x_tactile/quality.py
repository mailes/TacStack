"""Dataset health report for one OXT task.

What "quality" means for an offline archive: array completeness is
structural in zarr (there are no dropped frames), so the checkable signals
are monotonic timestamps, regular inter-frame steps, finite numeric payloads
and episode length stats. Per-sample drop / jitter metrics for live streams
arrive with the first live adapter (Phase 5); the scan is O(frames) and
decodes every compressed chunk of the scanned streams, so ``max_frames``
bounds the cost on real releases.
"""

from typing import Any

import numpy as np

from tacstack.adapters.open_x_tactile.archive import OpenXTactileTask


def assess_task(task: OpenXTactileTask, *, max_frames: int | None = None) -> dict[str, Any]:
    """Scan one task and return a JSON-safe health report.

    ``max_frames`` limits the per-stream payload scan (default: all frames).
    """
    ends = task.episode_ends()
    lengths = np.diff(np.concatenate(([0], ends)))
    total = int(ends[-1])
    scan = total if max_frames is None else min(max_frames, total)

    if "timestamps" in task.array_names:
        values = np.asarray(task.array("data/timestamps")[:scan])
        diffs = np.diff(values)
        timestamps_report: dict[str, Any] = {
            "scanned": int(values.size),
            "monotonic": bool(np.all(diffs >= 0)) if diffs.size else True,
            "unique_steps": sorted({int(v) for v in diffs.tolist()}) if diffs.size else [],
        }
    else:
        timestamps_report = {"scanned": 0, "monotonic": True, "unique_steps": []}

    streams: list[dict[str, Any]] = []
    for stream in task.streams():
        array = task.array(f"data/{stream.data_key}")
        frames = np.asarray(array[:scan])
        if frames.dtype.kind in "fiub":
            nonfinite: int | None = int((~np.isfinite(frames)).sum())
        else:
            nonfinite = None  # non-numeric payloads carry no finiteness signal
        streams.append(
            {
                "stream": stream.stream,
                "sensor": stream.sensor,
                "kind": stream.kind,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "frames_scanned": int(frames.shape[0]),
                "nonfinite": nonfinite,
            }
        )

    return {
        "task": task.name,
        "episodes": int(ends.size),
        "frames": total,
        "scanned_frames": scan,
        "episode_length": {
            "min": int(lengths.min()),
            "max": int(lengths.max()),
            "mean": float(lengths.mean()),
        },
        "timestamps": timestamps_report,
        "streams": streams,
    }
