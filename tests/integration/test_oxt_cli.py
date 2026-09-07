"""CLI integration tests for the Open-X-Tactile dataset commands."""

import json
from pathlib import Path

from mcap.reader import make_reader
from typer.testing import CliRunner

from tacstack.cli.main import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"

runner = CliRunner()


def test_dataset_list() -> None:
    result = runner.invoke(app, ["dataset", "list", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    assert "Wipe_Demo: episodes=3 frames=40" in result.output
    assert "right_gripper(GelSightMini,image,x2)" in result.output


def test_dataset_inspect_prints_descriptor_and_first_frame() -> None:
    result = runner.invoke(app, ["dataset", "inspect", str(FIXTURE), "--episode", "1"])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 2
    descriptor = json.loads(lines[0])
    assert descriptor["sensor_id"] == "oxt:Wipe_Demo:right_gripper"
    record = json.loads(lines[1])
    assert record["timestamp_ns"] == 10_000_000_000
    assert record["tactile_image"]["shape"] == [2, 32, 32, 3]
    assert record["raw"]["sub_task_instruction"] == "wipe the table"


def test_dataset_inspect_rejects_out_of_range_episode() -> None:
    result = runner.invoke(app, ["dataset", "inspect", str(FIXTURE), "--episode", "99"])
    assert result.exit_code == 1
    assert "error:" in result.stderr


def test_dataset_convert_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "episode.mcap"
    result = runner.invoke(
        app, ["dataset", "convert", str(FIXTURE), "--episode", "0", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "wrote 10 observations" in result.output
    with out.open("rb") as stream:
        reader = make_reader(stream)
        summary = reader.get_summary()
        assert summary.statistics.message_count == 10
        channels = {channel.id: channel for channel in summary.channels.values()}
        records = [
            (channels[message.channel_id].topic, json.loads(message.data))
            for _, _, message in reader.iter_messages()
        ]
    assert {topic for topic, _ in records} == {"tacstack/observations"}
    timestamps = [record["timestamp_ns"] for _, record in records]
    assert timestamps == sorted(timestamps)
    assert timestamps[-1] == 9_000_000_000
    assert records[0][1]["tactile_image"]["dtype"] == "uint8"
    assert records[0][1]["sensor"]["vendor"] == "Open-X-Tactile"
