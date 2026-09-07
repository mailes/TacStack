"""Commands available in the initial scaffold."""

import typer

from tacstack import __version__
from tacstack.core import TactileEvent
from tacstack.core.serialization import to_debug_json

app = typer.Typer(no_args_is_help=True, help="TacStack tactile contracts (development scaffold).")


@app.command()
def version() -> None:
    """Print the development version."""
    typer.echo(__version__)


@app.command()
def contract_demo() -> None:
    """Print a synthetic event to verify installation. No sensor or inference is used."""
    event = TactileEvent(
        timestamp_ns=0,
        sensor_id="synthetic",
        kind="contact_begin",
        probability=1.0,
        model_id="contract-example",
        latency_ms=0.0,
        metadata={"synthetic": True},
    )
    typer.echo(to_debug_json(event))


if __name__ == "__main__":
    app()
