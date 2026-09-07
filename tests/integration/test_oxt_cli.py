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
    assert "task_0001_Pick_Demo: episodes=2 frames=20" in result.output
    assert "right_gripper(uSkin,matrix,x2)" in result.output
    assert "right_grippertorque(ATIAxia80M20,state,x1)" in result.output


def test_dataset_inspect_prints_descriptor_and_first_frame() -> None:
    result = runner.invoke(
        app, ["dataset", "inspect", str(FIXTURE), "--task", "Wipe_Demo", "--episode", "1"]
    )
    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 2
    descriptor = json.loads(lines[0])
    assert descriptor["sensor_id"] == "oxt:Wipe_Demo:right_gripper"
    record = json.loads(lines[1])
    assert record["timestamp_ns"] == 10_000_000_000
    assert record["tactile_image"]["shape"] == [2, 32, 32, 3]
    assert record["raw"]["sub_task_instruction"] == "wipe the table"


def test_dataset_inspect_requires_task_when_ambiguous() -> None:
    result = runner.invoke(app, ["dataset", "inspect", str(FIXTURE)])
    assert result.exit_code == 1
    assert "multiple tasks" in result.stderr


def test_dataset_inspect_rejects_out_of_range_episode() -> None:
    result = runner.invoke(
        app, ["dataset", "inspect", str(FIXTURE), "--task", "Wipe_Demo", "--episode", "99"]
    )
    assert result.exit_code == 1
    assert "error:" in result.stderr


def test_dataset_convert_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "episode.mcap"
    result = runner.invoke(
        app,
        [
            "dataset",
            "convert",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--out",
            str(out),
        ],
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


def test_dataset_convert_taxel_episode(tmp_path: Path) -> None:
    out = tmp_path / "taxel.mcap"
    result = runner.invoke(
        app,
        [
            "dataset",
            "convert",
            str(FIXTURE),
            "--task",
            "task_0001_Pick_Demo",
            "--stream",
            "right_gripper",
            "--episode",
            "0",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "wrote 8 observations" in result.output
    with out.open("rb") as stream:
        records = [
            json.loads(message.data) for _, _, message in make_reader(stream).iter_messages()
        ]
    assert records[0]["taxels"]["shape"] == [2, 4, 4, 3]
    assert records[0]["taxels"]["dtype"] == "float32"
    assert records[0]["tactile_image"] is None
    assert records[0]["raw"]["robot_ft_base"] is not None
    assert records[0]["sensor"]["model"] == "uSkin"
