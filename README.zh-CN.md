# TacStack

[English](README.md) | 简体中文

面向机器人应用的跨传感器触觉语义与运行时项目。保留原始触觉数据，通过统一的
Observation、模型接口和 Event contract，逐步降低不同传感器的接入与使用成本。

**当前状态：Phase 0 / 开发脚手架。** 已实现核心 dataclass、基础验证、debug JSON、
Adapter / Model 协议和 CLI 安装验证。真实数据读取、contact/slip 检测、ONNX 推理、
Rerun / MCAP / ROS2 集成尚未实现。当前事件示例是人工构造的，不是模型输出。

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
  adapters/       # base 协议；OXT / MCAP / ROS2 / real_sensor 预留
  runtime/        # model 协议；buffer / ONNX backend 预留
  models/         # contact / slip 预留
  integrations/   # Rerun / MCAP / LeRobot / ROS2 预留
  benchmark/      # 评估工具预留
  cli/            # version / contract-demo
examples/         # 可运行 contract_demo，其余显式标注未实现
tests/            # unit / integration / fixtures
docs/             # 架构、接口、开发路线、ADR
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

1. 接入第一份 Open-X-Tactile 真实样本并记录来源与时间语义。
2. 增加第二种模态，验证 Observation contract。
3. 实现 Rerun 同步回放。
4. 加入 contact 与 temporal slip baseline、ONNX 和可复现评估。
5. 接入第一块真实传感器，验证 live record / replay / inference。

详见 [开发路线](docs/roadmap.md)、[架构](docs/architecture.md)、
[核心概念](docs/concepts.md)、[Adapter 指南](docs/adapters.md)、
[Runtime](docs/runtime.md)、[Benchmark](docs/benchmark.md) 和 [贡献指南](CONTRIBUTING.md)。

## 原则与许可

Raw-first · Semantics-first · Edge-first · Integration-first。
Core 不依赖 ROS2、云服务或训练框架；复用现有存储和可视化生态。

Apache-2.0，见 [LICENSE](LICENSE)。数据集、模型及第三方 SDK 的许可需分别核实。
