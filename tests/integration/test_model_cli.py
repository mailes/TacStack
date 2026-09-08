"""CLI integration tests for model run and benchmark."""

import json
from pathlib import Path

from typer.testing import CliRunner

from tacstack.cli.main import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "open_x_tactile" / "demo_wipe.tar"

runner = CliRunner()


def test_model_run_contact_prints_events() -> None:
    result = runner.invoke(
        app,
        [
            "model",
            "run",
            "contact",
            str(FIXTURE),
            "--task",
            "Wipe_Demo",
            "--episode",
            "0",
            "--stream",
            "right_gripper",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "summary: 10 frames," in result.output
    event_lines = [line for line in result.output.splitlines() if line.startswith("{")]
    events = [json.loads(line) for line in event_lines]
    assert events, "fixture episode should produce at least one transition"
    for event in events:
        assert event["model_id"] == "contact-baseline"
        assert event["kind"] in ("contact_begin", "contact_end")
        assert 0.0 <= event["probability"] <= 1.0
        assert "activity_value" in event["metadata"]


def test_model_run_slip_writes_json_array(tmp_path: Path) -> None:
    out = tmp_path / "events.json"
    result = runner.invoke(
        app,
        [
            "model",
            "run",
            "slip",
            str(FIXTURE),
            "--task",
            "task_0001_Pick_Demo",
            "--episode",
            "0",
            "--stream",
            "right_grippertorque",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"wrote {len(json.loads(out.read_text()))} events" in result.output
    events = json.loads(out.read_text())
    for event in events:
        assert event["model_id"] == "slip-baseline"
        assert event["kind"] in ("micro_slip", "slip")
        assert "diff_value" in event["metadata"]


def test_model_run_rejects_unknown_model(tmp_path: Path) -> None:
    result = runner.invoke(app, ["model", "run", "grief", str(FIXTURE)])
    assert result.exit_code == 1
    assert "unknown model" in result.output


def test_benchmark_is_reproducible_across_runs(tmp_path: Path) -> None:
    reports = []
    for run in range(2):
        out = tmp_path / f"report{run}.json"
        result = runner.invoke(
            app,
            [
                "benchmark",
                "contact",
                str(FIXTURE),
                "--task",
                "Wipe_Demo",
                "--stream",
                "right_gripper",
                "--out",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        report = json.loads(out.read_text())
        assert report["model"]["model_id"] == "contact-baseline"
        assert report["task"] == "Wipe_Demo"
        assert report["totals"]["episodes"] == 3
        assert report["totals"]["frames"] == 40
        reports.append(report)
    # event streams are deterministic; latency statistics vary between runs
    assert reports[0]["episodes"] == reports[1]["episodes"] or all(
        a["counts"] == b["counts"] and a["events"] == b["events"]
        for a, b in zip(reports[0]["episodes"], reports[1]["episodes"], strict=True)
    )
    assert reports[0]["totals"]["events"] == reports[1]["totals"]["events"]
    assert reports[0]["totals"]["counts"] == reports[1]["totals"]["counts"]
    for episode in reports[0]["episodes"]:
        assert episode["frames"] > 0
        assert episode["latency_ms_p95"] >= 0.0


def test_benchmark_requires_known_task(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "benchmark",
            "contact",
            str(FIXTURE),
            "--task",
            "nope",
            "--out",
            str(tmp_path / "r.json"),
        ],
    )
    assert result.exit_code == 1
    assert "not found" in result.output
