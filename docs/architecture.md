# Architecture

Sensor / Dataset → Adapter → TactileObservation → Window / Preprocess → Model → TactileEvent。
Rerun、MCAP、ROS2、LeRobot 为旁路或下游集成，不进入 core dependency。

当前只实现 core contracts 与 Adapter / Model Protocol；其余为路线图中的模块边界。
保留 sensor-specific raw，不把不同物理量强制映射成一个矩阵。
CalibrationSpec 当前只记录来源和参数，不执行标定。

见 [原始技术规划](plans/v0.1-development-plan.zh-CN.md) 与 [ADR](ADR/0001-scope-and-contracts.md)。
