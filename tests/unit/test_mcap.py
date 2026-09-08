import json
from pathlib import Path

import numpy as np

from tacstack import SensorDescriptor, TactileObservation
from tacstack.integrations.mcap import observation_record, write_episode_mcap


def _observation(taxels: np.ndarray) -> TactileObservation:
    sensor = SensorDescriptor("s", "v", "m", "taxel", "f", None, frozenset({"taxel_force"}))
    return TactileObservation(0, sensor, None, taxels=taxels)


def test_record_counts_nonfinite_and_stats_use_finite_values() -> None:
    observation = _observation(np.array([[1.0, float("nan")], [float("inf"), 3.0]]))
    summary = observation_record(observation)["taxels"]
    assert summary["shape"] == [2, 2]
    assert summary["nonfinite"] == 2
    assert summary["min"] == 1.0
    assert summary["max"] == 3.0
    json.dumps(observation_record(observation), allow_nan=False)


def test_record_all_nonfinite_has_null_statistics() -> None:
    observation = _observation(np.array([float("nan"), float("nan")]))
    summary = observation_record(observation)["taxels"]
    assert summary["nonfinite"] == 2
    assert summary["min"] is None
    assert summary["max"] is None
    assert summary["mean"] is None


def test_record_integer_arrays_report_zero_nonfinite() -> None:
    observation = _observation(np.array([[1, 2], [3, 4]], dtype=np.uint8))
    summary = observation_record(observation)["taxels"]
    assert summary["nonfinite"] == 0
    assert summary["min"] == 1.0
    assert summary["max"] == 4.0


def test_episode_with_nonfinite_taxels_writes_mcap(tmp_path: Path) -> None:
    out = tmp_path / "nonfinite.mcap"
    observations = [_observation(np.array([float("nan")])), _observation(np.array([0.5]))]
    summary = write_episode_mcap(observations, out)
    assert summary.messages == 2
    assert out.stat().st_size > 0
