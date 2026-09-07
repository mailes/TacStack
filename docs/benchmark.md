# Benchmark plan

尚未实现 benchmark CLI 或模型评估。当前测试仅验证软件 contract。
后续报告需记录 dataset / split / sensor / calibration / model / threshold / runtime 版本。
按 sensor 与模型分组统计误报、漏报、事件检测延迟及 p95 pipeline latency。
区分推理耗时和端到端检测延迟；按 episode / object 隔离训练与测试，避免相邻帧泄漏。
不把 synthetic contract demo 作为模型性能证据。
