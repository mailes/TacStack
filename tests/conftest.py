import pytest

from tacstack import SensorDescriptor


@pytest.fixture
def sensor() -> SensorDescriptor:
    return SensorDescriptor(
        "fixture", "test", "taxel", "taxel", "sensor", 30.0, frozenset({"taxel_force"})
    )
