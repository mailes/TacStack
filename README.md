# TacStack

English | [简体中文](README.zh-CN.md)

Cross-sensor tactile semantics and runtime for robotics. TacStack keeps raw
tactile data intact and layers a unified Observation, model interface and Event
contract on top, steadily lowering the cost of bringing up and using different
tactile sensors.

**Status: Phase 4 done / Phase 5 (first live sensor) in preparation.** The
offline loop works end to end — dataset → `TactileObservation` → MCAP / Rerun
replay → contact / slip events (builtin or ONNX scoring) → benchmark report.
Observation streams export to and replay from LeRobot v3.0 dataset directories
(taxel features), riding that ecosystem's tooling directly. Protocol layers
for five real sensors are implemented and tested offline
([Verified sensor protocols](#verified-sensor-protocols)): four serial codecs
verified byte-for-byte against their vendor manuals, plus the Meta DIGIT
vision-tactile identity / semantics layer. Live adapters land with the
hardware (Phase 5). ROS2 integration is not implemented yet; the
bundled dataset fixture is synthetic (`tests/fixtures/README.md`).

## Getting started

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install from source
for now; no PyPI package yet.

```bash
git clone https://github.com/mailes/TacStack.git
cd TacStack
uv sync
uv run tacstack version
uv run tacstack contract-demo
uv run tacstack demo
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

## Verified sensor protocols

Five real sensor protocol layers ship hardware-free. Four are pure codec
layers — frame building and parsing, checksums, register decoding — verified
byte-for-byte against the worked example frames in their vendor manuals. The
fifth is the Meta DIGIT vision-tactile layer: device identity, raw-frame to
observation mapping and reference-frame contact / slip tracking. All are
pinned by unit tests with no hardware required. Live capture adapters plus
live record / replay / inference are the Phase 5 deliverables once the
hardware arrives.

| Sensor | Output | Link | Codec | Notes |
|---|---|---|---|---|
| M0404S serial matrix kit | 4×4 resistive matrix, 16 taxels | UART 115200 8N1, active push | `adapters/real_sensor/m0404s.py` | 35-byte frames, additive checksum |
| PaXini PX-6AX GEN3 | per-point 3-axis force + resultant, 0.1 N/LSB | UART 921600, request–response | `adapters/real_sensor/paxini.py` | register protocol, two's-complement LRC |
| PaXini PX6D | six-axis F/T wrench (Fx, Fy, Fz, Mx, My, Mz), float32 | USB / RS485 (CAN shares the command set) | `adapters/real_sensor/px6d.py` | auto-report up to 1 kHz; request CRC8 recovered from manual samples |
| PaXini PX3Q | 3-axis joint torque Mx / My / Mz in N·m (30 / 50 / 100 N·m full scale by model) | USB / RS485, 921600 8N1 | `adapters/real_sensor/px3q.py` | 1 kHz sampling; CAN envelope documented but deferred, USB-first |
| Meta DIGIT | 320×240 RGB gel image (vision-based tactile) | USB UVC, QVGA 60 fps (default) / VGA 30 fps | `adapters/real_sensor/digit.py` | open hardware; identity + semantics layer, live capture lands with hardware |

Request-frame checksums are pinned by the manuals' example frames. Where a
rule cannot be recovered from documentation alone (the response-frame CRC on
PX6D / PX3Q), parsing stays lenient and the open gap is recorded in the module
docstring until captured hardware traffic settles it. Selection criteria and
buy-time caveats live in
[docs/plans/sensor-procurement.zh-CN.md](docs/plans/sensor-procurement.zh-CN.md).

## Project layout

```text
src/tacstack/
  core/           # data structures, basic validation, debug serialization
  adapters/       # base protocol; open_x_tactile + mcap replay + real_sensor codecs + DIGIT semantics implemented
  runtime/        # model protocol; buffer / ONNX backend reserved
  models/         # contact / slip reserved
  integrations/   # MCAP export + Rerun replay + LeRobot v3.0 dataset export implemented; ROS2 reserved
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

1. Bring up the first real sensor end to end — live adapter, live record /
   replay / inference, 30-minute stability (Phase 5).
2. Docs, external Quickstart and the v0.1 release (Phase 6).

Runnable walkthroughs: [Tutorial 1 - offline pipeline](docs/tutorials/tutorial-1-offline-pipeline.zh-CN.md)
and [Tutorial 2 - visualize & annotate](docs/tutorials/tutorial-2-visualize-annotate.zh-CN.md).
See also the [roadmap](docs/roadmap.md), [architecture](docs/architecture.md),
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
