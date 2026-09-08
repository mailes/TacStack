"""Reproducible benchmark harness for runtime models.

Runs a model over observation streams and summarizes the event stream:
per-episode frame counts, event counts by kind, and latency statistics.
Reproducibility contract: the same input stream with the same model
parameters produces identical event kinds, probabilities and ordering;
latency statistics are wall-clock measurements and vary between runs.
Quality metrics against labeled data are out of scope for v0.1.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import ceil
from typing import Any

from tacstack.core import TactileEvent, TactileObservation
from tacstack.core.serialization import to_debug_dict
from tacstack.runtime.pipeline import Runtime, TactileModel


@dataclass(frozen=True)
class EpisodeSummary:
    """One episode's event stream summary."""

    episode: int
    frames: int
    events: int
    counts: dict[str, int]
    latency_ms_mean: float
    latency_ms_p50: float
    latency_ms_p95: float


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (q in [0, 100]); 0.0 for empty input."""
    if not values:
        return 0.0
    if not 0 <= q <= 100:
        raise ValueError("q must be within [0, 100]")
    ordered = sorted(values)
    rank = max(1, ceil(q / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarize_events(
    events: Sequence[TactileEvent], *, episode: int, frames: int
) -> EpisodeSummary:
    """Summarize one episode's event stream."""
    counts: dict[str, int] = {}
    latencies: list[float] = []
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
        latencies.append(event.latency_ms)
    return EpisodeSummary(
        episode=episode,
        frames=frames,
        events=len(events),
        counts=counts,
        latency_ms_mean=sum(latencies) / len(latencies) if latencies else 0.0,
        latency_ms_p50=percentile(latencies, 50),
        latency_ms_p95=percentile(latencies, 95),
    )


def benchmark_episodes(
    model: TactileModel,
    episodes: Iterable[tuple[int, Iterable[TactileObservation]]],
    *,
    window_frames: int,
) -> dict[str, Any]:
    """Run the model over every (episode, observations) pair; JSON-safe report.

    A fresh Runtime (and therefore fresh model event state) is built per
    episode so runs are independent and reproducible.
    """
    episode_reports: list[EpisodeSummary] = []
    totals: dict[str, int] = {}
    total_frames = 0
    total_events = 0
    for episode_index, observations in episodes:
        runtime = Runtime(model, window_frames=window_frames)
        collected: list[TactileEvent] = []
        frames = 0
        for observation in observations:
            frames += 1
            collected.extend(runtime.process(observation))
        summary = summarize_events(collected, episode=episode_index, frames=frames)
        episode_reports.append(summary)
        total_frames += frames
        total_events += summary.events
        for kind, count in summary.counts.items():
            totals[kind] = totals.get(kind, 0) + count
    return {
        "model": to_debug_dict(model.manifest),
        "window_frames": window_frames,
        "episodes": [to_debug_dict(vars(summary)) for summary in episode_reports],
        "totals": {
            "episodes": len(episode_reports),
            "frames": total_frames,
            "events": total_events,
            "counts": totals,
        },
    }
