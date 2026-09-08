# TacStack

[English](README.md) | 简体中文

面向机器人应用的跨传感器触觉语义与运行时项目。保留原始触觉数据，通过统一的
Observation、模型接口和 Event contract，逐步降低不同传感器的接入与使用成本。

**当前状态：Phase 1 完成 / Phase 2 完成（演示视频待录）。** 核心 dataclass、基础验证、
debug JSON、Adapter / Model 协议已就绪，第一条真实数据通路可用：Open-X-Tactile
（FTP-1）适配器把 tar 包裹的 zarr episode 读取为统一 `TactileObservation`，同时
支持两类负载——视触觉图像流（GelSight）与 taxel 流（uSkin matrix、ATIAxia80M20
力扭矩）；CLI 可 list / inspect / convert episode，转换输出 Foxglove 可打开的
MCAP 记录，`tacstack replay` 输出同步时间轴的 Rerun 录制，`tacstack annotate`
把 C/S/U 标记存为 Parquet 并可回放到时间轴（`rerun` / `annotate` 为可选依赖）。
contact/slip 检测、ONNX 推理、ROS2 集成和真实传感器尚未实现。仓库内置
的数据集 fixture 是合成内容，布局镜像真实发布格式（见 `tests/fixtures/README.md`）。

## 本地开始

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。目前从源码安装，尚未发布 PyPI 包。

```bash
git clone https://github.com/mailes/TacStack.git
cd TacStack
uv sync
uv run tacstack version
uv run tacstack contract-demo
uv run python examples/contract_demo.py
```

`contract-demo` 输出一个带 `synthetic: true` 的 JSON 事件，不下载数据、不连接硬件。

同一套 Observation contract 也能回放本地 tar 或解包目录里的 Open-X-Tactile
episode（CI 和下面的示例只使用内置合成 fixture，不下载数据）：

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

## 项目结构

```text
src/tacstack/
  core/           # 数据结构、基础验证、debug serialization
  adapters/       # base 协议；open_x_tactile 已实现（tar/zarr，Phase 1）
  runtime/        # model 协议；buffer / ONNX backend 预留
  models/         # contact / slip 预留
  integrations/   # MCAP 导出 + Rerun 回放已实现；LeRobot / ROS2 预留
  benchmark/      # 评估工具预留
  cli/            # version / contract-demo / dataset list-inspect-convert / replay / annotate
examples/         # 可运行 contract_demo 与 replay_open_x_tactile
tests/            # unit / integration / fixtures
docs/             # 架构、接口、开发路线、ADR
scripts/          # 开发工具（fixture 生成器）
.github/workflows/ci.yml
```

## 开发检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not hardware"
uv build
uv run pre-commit install
```

## 下一步

1. 加入 contact 与 temporal slip baseline、ONNX 和可复现评估（Phase 3）。
2. 接入第一块真实传感器，验证 live record / replay / inference。

详见 [开发路线](docs/roadmap.md)、[架构](docs/architecture.md)、
[核心概念](docs/concepts.md)、[Adapter 指南](docs/adapters.md)、
[Runtime](docs/runtime.md)、[Benchmark](docs/benchmark.md) 和 [贡献指南](CONTRIBUTING.md)。

## 原则与许可

Raw-first · Semantics-first · Edge-first · Integration-first。
Core 不依赖 ROS2、云服务或训练框架；复用现有存储和可视化生态。

Apache-2.0，见 [LICENSE](LICENSE)。数据集、模型及第三方 SDK 的许可需分别核实。
