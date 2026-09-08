# Development roadmap

沿用原始 12 周计划。Phase 0 / Phase 1 已完成。

| 阶段 | 目标 | 状态 |
|---|---|---|
| 0 | package、core contracts、验证、CI、ADR | 已完成 |
| 1 | 2–3 类 OXT 数据、MCAP 通路 | 已完成（图像 + matrix + F/T 三种流，真实 tar 验证） |
| 2 | Rerun 回放与轻量标注 | 已完成（`TactileEvent` marker 随 Phase 3；演示视频待录） |
| 3 | contact / slip baseline、ONNX、benchmark | 已完成（Runtime + builtin/ONNX 双后端 + benchmark；质量指标待标注数据） |
| 4 | 跨模态事件、标定与质量追踪 | 进行中（capability 校验、quality 报告、benchmark 分组已通；标定贯通与 drop/jitter 待做） |
| 5 | 第一块真实传感器 live inference | 待实现 |
| 6 | 文档、外部用户 Quickstart、v0.1 release | 待实现 |

下一项：Phase 4 收尾 —— CalibrationSpec 贯通（adapter → observation → 事件
metadata）、drop/jitter 指标补全、Week-4 Go/No-Go 对照检查。
完整任务与决策点见 [原始技术规划](plans/v0.1-development-plan.zh-CN.md)。
原始规划中的命令描述目标版本能力，不代表当前已可运行。
