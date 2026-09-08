"""Run the built-in temporal slip baseline over one fixture episode.

Zero downloads, zero hardware: the episode comes from the committed synthetic
fixture. The F/T stream oscillates, so frame differences cross the micro
slip threshold repeatedly; point SOURCE at a real Open-X-Tactile tar to run
the same code on real data.
"""

from pathlib import Path

from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

SOURCE = Path(__file__).parents[1] / "tests" / "fixtures" / "open_x_tactile" / "demo_wipe.tar"


def main() -> None:
    adapter = OpenXTactileAdapter(
        SOURCE,
        task="task_0001_Pick_Demo",
        episode=0,
        stream="right_grippertorque",
        rate_hz=30.0,
    )
    model = builtin_model("slip", micro_threshold=0.4, slip_threshold=0.7)
    runtime = Runtime(model, window_frames=2)
    adapter.open()
    counts: dict[str, int] = {}
    try:
        for event in runtime.events(observations(adapter)):
            counts[event.kind] = counts.get(event.kind, 0) + 1
            print(
                f"t={event.timestamp_ns} {event.kind} p={event.probability:.3f} "
                f"latency={event.latency_ms:.3f}ms"
            )
    finally:
        adapter.close()
    print(f"summary: {counts or 'no rising-edge crossings with these thresholds'}")


if __name__ == "__main__":
    main()
