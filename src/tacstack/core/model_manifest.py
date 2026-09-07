"""Model requirements, independent of the inference implementation."""

from dataclasses import dataclass

from tacstack.core.descriptor import SensorDescriptor


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    version: str
    task: str
    required_capabilities: frozenset[str]
    window_ms: int
    runtime: str
    artifact_uri: str
    calibration_requirement: str | None = None

    def __post_init__(self) -> None:
        if type(self.window_ms) is not int or self.window_ms <= 0:
            raise ValueError("window_ms must be a positive Python integer")
        if not all(x.strip() for x in (self.model_id, self.version, self.task, self.runtime)):
            raise ValueError("model identity, task and runtime must not be empty")

    def validate_capabilities(self, sensor: SensorDescriptor) -> None:
        missing = self.required_capabilities - sensor.capabilities
        if missing:
            raise ValueError(f"Missing sensor capabilities: {', '.join(sorted(missing))}")
