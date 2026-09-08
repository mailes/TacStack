# Development roadmap

沿用原始 12 周计划。Phase 0 / Phase 1 已完成。

| 阶段 | 目标 | 状态 |
|---|---|---|
| 0 | package、core contracts、验证、CI、ADR | 已完成 |
| 1 | 2–3 类 OXT 数据、MCAP 通路 | 已完成（图像 + matrix + F/T 三种流，真实 tar 验证） |
| 2 | Rerun 回放与轻量标注 | 回放链已通；标注（annotations.parquet）待做 |
| 3 | contact / slip baseline、ONNX、benchmark | 待实现 |
| 4 | 跨模态事件、标定与质量追踪 | 待实现 |
| 5 | 第一块真实传感器 live inference | 待实现 |
| 6 | 文档、外部用户 Quickstart、v0.1 release | 待实现 |

下一项：完成 Phase 2 的轻量标注（C/S/U → `annotations.parquet`），随后进入
Phase 3（slip baseline runtime，Issue #5）。
完整任务与决策点见 [原始技术规划](plans/v0.1-development-plan.zh-CN.md)。
原始规划中的命令描述目标版本能力，不代表当前已可运行。
