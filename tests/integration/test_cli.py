import json

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
