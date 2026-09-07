# Contributing

欢迎中文或英文 issue / PR。先按 README 执行 `uv sync` 和全部开发检查。
当前优先完成 docs/roadmap.md 中的 Phase 0 / Phase 1。

- Core 保持轻量，厂商字段放 raw / metadata，重型依赖放未来可选集成。
- 新 Adapter 需要小型合法 fixture、来源说明、时间戳规则和集成测试。
- 不在 CI 下载完整数据或要求硬件；硬件测试使用 `pytest.mark.hardware`。
- 提交前运行 lint、format、type check、pytest 和 build。
- 行为或接口决策记录到 docs/ADR/；API 当前为实验性。
- 不提交凭据、客户数据、大模型文件或不明授权样本。
