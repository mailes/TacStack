"""Replay one Open-X-Tactile episode through the unified Observation contract.

Uses the committed golden fixture so it runs offline without any dataset
download. Point SOURCE at a real FTP-1 tar (for example VLA_touch.tar) or an
extracted `<task>.zarr` directory to replay real data.
"""

from pathlib import Path

from tacstack.adapters.base import observations
from tacstack.adapters.open_x_tactile import OpenXTactileAdapter
from tacstack.core.serialization import to_debug_json

SOURCE = Path(__file__).parents[1] / "tests" / "fixtures" / "open_x_tactile" / "demo_wipe.tar"


def main() -> None:
    adapter = OpenXTactileAdapter(SOURCE, task="Wipe_Demo", episode=0, rate_hz=30.0)
    adapter.open()
    try:
        print("sensor:", to_debug_json(adapter.descriptor()))
        for observation in observations(adapter):
            image = observation.tactile_image
            shape = None if image is None else list(image.shape)
            frame = observation.metadata["oxt_frame_index"]
            print(f"t={observation.timestamp_ns} frame={frame} tactile_image={shape}")
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
