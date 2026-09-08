# TacStack

[English](README.md) | 简体中文

面向机器人应用的跨传感器触觉语义与运行时项目。保留原始触觉数据，通过统一的
Observation、模型接口和 Event contract，逐步降低不同传感器的接入与使用成本。

**当前状态：Phase 4 完成 / Phase 5（首块真实传感器）准备中。** 离线链路已端到端
打通：数据集 → `TactileObservation` → MCAP / Rerun 回放 → contact / slip 事件
（builtin / ONNX 双打分后端）→ benchmark 报告。观测流可导出为 LeRobot v3.0
数据集目录并直接回放（taxel 特征），直接复用其生态工具链。五款真实传感器的
协议层均已离线验证（见[已验证的传感器协议](#已验证的传感器协议)）：四款串口
编解码按厂商手册逐字节黄金测试，另有 Meta DIGIT 视觉触觉传感器的身份识别与
语义层。实时适配器待硬件到货（Phase 5）。ROS2 集成尚未实现；内置数据集
fixture 为合成内容（`tests/fixtures/README.md`）。

## 本地开始

需要 Python 3.12+。[PyPI](https://pypi.org/project/tacstack/) 已发布 alpha
预发布版；引导式 demo 与内置样本需要源码仓库。

```bash
pip install --pre tacstack
tacstack version
tacstack contract-demo
```

`contract-demo` 输出一个带 `synthetic: true` 的 JSON 事件，不下载数据、不连接硬件。
可选组件：`pip install --pre "tacstack[rerun,onnx]"`。

开发方式（含引导式 `tacstack demo`、内置样本与 Rerun 回放）：

```bash
git clone https://github.com/mailes/TacStack.git
cd TacStack
uv sync --extra rerun
uv run tacstack demo
uv run python examples/contract_demo.py
```

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

## 已验证的传感器协议

五款真实传感器的协议层均以硬件无关形式落地：四款为纯 codec 层——帧构建/解析、
校验、寄存器解码——全部按厂商手册中的示例帧逐字节对照；第五款是 Meta DIGIT
视觉触觉层：设备身份识别、原始帧到 Observation 的映射、参考帧接触 / 滑动追踪。
以上全部由单元测试钉死，不需要硬件即可完整验证。实时采集适配器与 live record /
replay / inference 是 Phase 5 的交付，待硬件到货。

| 传感器 | 输出 | 链路 | Codec | 备注 |
|---|---|---|---|---|
| 洛城电子/冠拓电子 M0404S | 4×4 压阻矩阵，16 taxel | UART 115200 8N1，主动上报 | `adapters/real_sensor/m0404s.py` | 35 字节帧，累加和校验 |
| 帕西尼 PX-6AX GEN3 | 逐测点三轴力 + 合力，0.1 N/LSB | UART 921600，请求-应答 | `adapters/real_sensor/paxini.py` | 寄存器协议，二补数 LRC |
| 帕西尼 PX6D | 六维力扭矩 (Fx, Fy, Fz, Mx, My, Mz)，float32 | USB / RS485（CAN 同命令集） | `adapters/real_sensor/px6d.py` | 自动回传最高 1 kHz；请求 CRC8 由手册样例反推 |
| 帕西尼 PX3Q | 三轴关节扭矩 Mx/My/Mz（N·m，按型号 30/50/100 N·m 满量程） | USB / RS485，921600 8N1 | `adapters/real_sensor/px3q.py` | 采样 1 kHz；CAN 封装手册有定义、暂缓实现（USB 为主） |
| Meta DIGIT | 320×240 RGB 凝胶图像（视觉触觉） | USB UVC，QVGA 60fps（默认）/ VGA 30fps | `adapters/real_sensor/digit.py` | 开放硬件；身份 + 语义层，live 采集随硬件落地 |

请求帧校验算法均由手册示例帧钉死。个别无法仅凭文档恢复的规则（PX6D / PX3Q
的应答帧 CRC），解析保持宽松，缺口记录在各模块 docstring，待实测字节流确认。
选型要求与下单注意事项见
[docs/plans/sensor-procurement.zh-CN.md](docs/plans/sensor-procurement.zh-CN.md)。

## 项目结构

```text
src/tacstack/
  core/           # 数据结构、基础验证、debug serialization
  adapters/       # base 协议；open_x_tactile + mcap replay + real_sensor 编解码 + DIGIT 语义已实现
  runtime/        # model 协议；buffer / ONNX backend 预留
  models/         # contact / slip 预留
  integrations/   # MCAP 导出 + Rerun 回放 + LeRobot v3.0 数据集导出已实现；ROS2 预留
  benchmark/      # 评估工具预留
  cli/            # version / contract-demo / dataset / replay / annotate / model run / benchmark
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

1. 第一块真实传感器端到端接入：live 适配器、live record / replay / inference、
   30 分钟稳定性（Phase 5）。
2. 文档、外部用户 Quickstart 与 v0.1 release（Phase 6）。

可运行教程：[Tutorial 1 - 离线管线](docs/tutorials/tutorial-1-offline-pipeline.zh-CN.md)、
[Tutorial 2 - 可视化与标注](docs/tutorials/tutorial-2-visualize-annotate.zh-CN.md)。
详见 [开发路线](docs/roadmap.md)、[架构](docs/architecture.md)、
[核心概念](docs/concepts.md)、[Adapter 指南](docs/adapters.md)、
[Runtime](docs/runtime.md)、[Benchmark](docs/benchmark.md) 和 [贡献指南](CONTRIBUTING.md)。

## 原则与许可

Raw-first · Semantics-first · Edge-first · Integration-first。
Core 不依赖 ROS2、云服务或训练框架；复用现有存储和可视化生态。

Apache-2.0，见 [LICENSE](LICENSE)。数据集、模型及第三方 SDK 的许可需分别核实。
