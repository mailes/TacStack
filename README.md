# TacStack

English | [简体中文](README.zh-CN.md)

Cross-sensor tactile semantics and runtime for robotics. TacStack keeps raw
tactile data intact and layers a unified Observation, model interface and Event
contract on top, steadily lowering the cost of bringing up and using different
tactile sensors.

**Status: Phase 2 done / Phase 3 runtime in progress.** Core dataclasses,
basic validation, debug JSON and the Adapter / Model protocols are in place, and
the first real data path works: the Open-X-Tactile (FTP-1) adapter reads
tar-wrapped zarr episodes into `TactileObservation` for both payload kinds —
vision-tactile image streams (GelSight) and taxel streams (uSkin matrix,
ATIAxia80M20 force/torque) — the CLI can list / inspect / convert episodes,
conversion writes an MCAP record that Foxglove opens, `tacstack replay` writes
a synchronized Rerun recording, and `tacstack annotate` stores C / S / U marks
as Parquet that replay puts back on the timeline (`rerun` / `annotate` are
opt-in extras). Phase 3 is done: `for event in runtime.events(...)` drives
built-in heuristic contact / slip baselines through both the builtin scorer
and ONNX scoring artifacts (onnxruntime backend, artifact/manifest
separation; deterministic threshold models — not learned), and `tacstack
benchmark` produces reproducible per-episode reports. Phase 4 is in progress:
two-level capability validation, the `dataset quality` health report and
per-stream benchmark grouping are in. The ROS2
integration and live sensors are not implemented yet. The bundled dataset
fixture is synthetic; its layout mirrors the real releases (see
`tests/fixtures/README.md`).

## Getting started

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install from source
for now; no PyPI package yet.

```bash
git clone https://github.com/mailes/TacStack.git
cd TacStack
uv sync
uv run tacstack version
uv run tacstack contract-demo
uv run python examples/contract_demo.py
```

`contract-demo` prints one JSON event flagged `synthetic: true`. It downloads no
data and touches no hardware.

The same Observation contract also replays real Open-X-Tactile episodes from a
local tar or extracted directory (CI and the example below use only the bundled
synthetic fixture):

```bash
uv run tacstack dataset list tests/fixtures/open_x_tactile/demo_wipe.tar
uv run tacstack dataset inspect tests/fixtures/open_x_tactile/demo_wipe.tar --task Wipe_Demo --episode 0
uv run tacstack dataset convert tests/fixtures/open_x_tactile/demo_wipe.tar --task Wipe_Demo --episode 0 --out demo.mcap
uv run python examples/replay_open_x_tactile.py
```

```python
from tacstack import TactileEvent

sample = TactileEvent(
    timestamp_ns=0,
    sensor_id="synthetic",
    kind="contact_begin",
    probability=1.0,
    model_id="contract-example",
    latency_ms=0.0,
)
```

## Project layout

```text
src/tacstack/
  core/           # data structures, basic validation, debug serialization
  adapters/       # base protocol; open_x_tactile implemented (tar/zarr, Phase 1)
  runtime/        # model protocol; buffer / ONNX backend reserved
  models/         # contact / slip reserved
  integrations/   # MCAP export + Rerun replay implemented; LeRobot / ROS2 reserved
  benchmark/      # evaluation tooling reserved
  cli/            # version / contract-demo / dataset / replay / annotate / model run / benchmark
examples/         # runnable contract_demo and replay_open_x_tactile
tests/            # unit / integration / fixtures
docs/             # architecture, interfaces, roadmap, ADR (Chinese for now)
scripts/          # development tools (fixture generator)
.github/workflows/ci.yml
```

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not hardware"
uv build
uv run pre-commit install
```

## Next steps

1. Cross-sensor calibration, quality tracking and labeled-data evaluation (Phase 4).
2. Bring up the first real sensor and verify live record / replay / inference.

See the [roadmap](docs/roadmap.md), [architecture](docs/architecture.md),
[concepts](docs/concepts.md), [adapter guide](docs/adapters.md),
[runtime](docs/runtime.md), [benchmark](docs/benchmark.md) and the
[contribution guide](CONTRIBUTING.md). Most of these docs are Chinese for now;
English translations will follow before the v0.1 release.

## Principles and license

Raw-first · Semantics-first · Edge-first · Integration-first.
Core depends on neither ROS2, cloud services nor training frameworks; reuse the
existing storage and visualization ecosystems.

Apache-2.0, see [LICENSE](LICENSE). Dataset, model and third-party SDK licenses
must be verified separately.
