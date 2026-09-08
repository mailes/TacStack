import json
from pathlib import Path

from typer.testing import CliRunner

from tacstack.cli.main import app

runner = CliRunner()


def test_contract_demo() -> None:
    result = runner.invoke(app, ["contract-demo"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "contact_begin"
    assert payload["metadata"]["synthetic"] is True


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0.dev0"


def test_demo_command_writes_artifacts(tmp_path: Path) -> None:
    result = runner.invoke(app, ["demo", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Demo complete" in result.output
    assert "[2/4] mcap: 15 embedded frames" in result.output
    for name in ("quality.json", "tactile.mcap", "events.json", "tactile.rrd"):
        assert (tmp_path / name).exists(), f"missing demo artifact: {name}"
    events = json.loads((tmp_path / "events.json").read_text())
    assert events, "demo should record at least one TactileEvent"
