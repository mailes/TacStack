"""Built-in model implementations and the named-model factory.

The built-ins are deterministic heuristics that validate the runtime and
event contract; they are not learned models and their defaults are
uncalibrated. ONNX artifact loading is planned for Phase 3.
"""

from tacstack.models.contact import ContactBaseline, contact_baseline_manifest
from tacstack.models.slip import SlipBaseline, slip_baseline_manifest

__all__ = [
    "ContactBaseline",
    "SlipBaseline",
    "builtin_model",
    "contact_baseline_manifest",
    "slip_baseline_manifest",
]


def builtin_model(name: str, **params: object) -> ContactBaseline | SlipBaseline:
    """Build a named built-in model ("contact" or "slip") with keyword params."""
    builders: dict[str, type[ContactBaseline | SlipBaseline]] = {
        "contact": ContactBaseline,
        "slip": SlipBaseline,
    }
    try:
        builder = builders[name]
    except KeyError:
        available = ", ".join(sorted(builders))
        raise KeyError(f"unknown built-in model {name!r}; available: {available}") from None
    return builder(**params)  # type: ignore[arg-type]
