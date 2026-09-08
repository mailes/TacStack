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


def test_replay_writes_rrd_and_logs_matching_annotations(tmp_path: Path) -> None:
    from tacstack.annotations import AnnotationLog, TactileMark, now_ns

    marks = tmp_path / "marks.parquet"
    log = AnnotationLog(marks)
    log.add(
        TactileMark(
            source=str(FIXTURE),
            task="Wipe_Demo",
            episode=0,
            stream="right_gripper",
            frame_index=2,
            oxt_frame_index=2,
            timestamp_ns=2_000_000_000,
            mark="S",
            user="tester",
            created_ns=now_ns(),
        )
    )
    out = tmp_path / "replay.rrd"
    result = runner.invoke(
        app,
        [
            "replay",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--stream",
            "right_gripper",
            "--out",
            str(out),
            "--annotations",
            str(marks),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "logged 10 observations" in result.output
    assert "and 1 annotations" in result.output
    assert out.stat().st_size > 0


def test_replay_logs_no_annotations_when_stream_differs(tmp_path: Path) -> None:
    from tacstack.annotations import AnnotationLog, TactileMark, now_ns

    marks = tmp_path / "marks.parquet"
    log = AnnotationLog(marks)
    log.add(
        TactileMark(
            source=str(FIXTURE),
            task="Wipe_Demo",
            episode=0,
            stream="other_stream",
            frame_index=2,
            oxt_frame_index=2,
            timestamp_ns=2_000_000_000,
            mark="C",
            user="tester",
            created_ns=now_ns(),
        )
    )
    out = tmp_path / "replay.rrd"
    result = runner.invoke(
        app,
        [
            "replay",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--stream",
            "right_gripper",
            "--out",
            str(out),
            "--annotations",
            str(marks),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "and 0 annotations" in result.output


def test_annotate_add_then_show(tmp_path: Path) -> None:
    from tacstack.annotations import AnnotationLog

    marks = tmp_path / "marks.parquet"
    added = runner.invoke(
        app,
        [
            "annotate",
            "add",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "1",
            "--stream",
            "right_gripper",
            "--frame",
            "6",
            "--mark",
            "slip",
            "--user",
            "tester",
            "--out",
            str(marks),
        ],
    )
    assert added.exit_code == 0, added.output
    assert "marked right_gripper frame 6 as S (slip); 1 marks" in added.output
    # Wipe_Demo episode ends are [10, 25, 40]: frame 6 of episode 1 is
    # absolute frame 10 + 6 = 16, timestamp 16s
    stored = AnnotationLog(marks).marks()[0]
    assert stored.oxt_frame_index == 16
    assert stored.timestamp_ns == 16_000_000_000

    shown = runner.invoke(app, ["annotate", "show", str(marks)])
    assert shown.exit_code == 0, shown.output
    assert "S Wipe_Demo ep1 right_gripper frame=6 (oxt 16" in shown.output
    assert "1 marks, schema 1.0" in shown.output


def test_annotate_add_rejects_out_of_range_frame(tmp_path: Path) -> None:
    marks = tmp_path / "marks.parquet"
    result = runner.invoke(
        app,
        [
            "annotate",
            "add",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--stream",
            "right_gripper",
            "--frame",
            "999",
            "--mark",
            "C",
            "--user",
            "tester",
            "--out",
            str(marks),
        ],
    )
    assert result.exit_code == 1
    assert "out of range" in result.output


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
