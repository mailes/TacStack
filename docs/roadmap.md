# Development roadmap

沿用原始 12 周计划。Phase 0 / Phase 1 已完成。

| 阶段 | 目标 | 状态 |
|---|---|---|
| 0 | package、core contracts、验证、CI、ADR | 已完成 |
| 1 | 2–3 类 OXT 数据、MCAP 通路 | 已完成（图像 + matrix + F/T 三种流，真实 tar 验证） |
| 2 | Rerun 回放与轻量标注 | 已完成（`TactileEvent` marker 随 Phase 3；演示视频待录） |
| 3 | contact / slip baseline、ONNX、benchmark | 已完成（Runtime + builtin/ONNX 双后端 + benchmark；质量指标待标注数据） |
| 4 | 跨模态事件、标定与质量追踪 | 已完成（capability 校验、quality 报告、标定贯通、benchmark 分组；Week-8 Go/No-Go 对照待做） |
| 5 | 第一块真实传感器 live inference | 待实现 |
| 6 | 文档、外部用户 Quickstart、v0.1 release | 待实现 |

下一项：Phase 5 —— 第一块真实传感器（采购中）：live adapter、设备断连/重连、
live Rerun 与 live contact/slip 推理、本地 MCAP 记录、30 分钟稳定性。
完整任务与决策点见 [原始技术规划](plans/v0.1-development-plan.zh-CN.md)。
原始规划中的命令描述目标版本能力，不代表当前已可运行。
