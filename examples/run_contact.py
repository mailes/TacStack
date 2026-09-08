"""Run the built-in contact baseline over one fixture episode.

Zero downloads, zero hardware: the episode comes from the committed synthetic
fixture. The same three lines of runtime code work on a real Open-X-Tactile
tar — point SOURCE at it and pick task / episode / stream.
"""

from pathlib import Path

from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

SOURCE = Path(__file__).parents[1] / "tests" / "fixtures" / "open_x_tactile" / "demo_wipe.tar"


def main() -> None:
    adapter = OpenXTactileAdapter(
        SOURCE, task="Wipe_Demo", episode=1, stream="right_gripper", rate_hz=30.0
    )
    model = builtin_model("contact", on_threshold=0.99, off_threshold=0.9)
    runtime = Runtime(model, window_frames=1)
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
    print(f"summary: {counts or 'no transitions with these thresholds'}")


if __name__ == "__main__":
    main()
