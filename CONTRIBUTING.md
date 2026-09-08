# Contributing

欢迎中文或英文 issue / PR。先按 README 执行 `uv sync` 和全部开发检查。
当前优先完成 [开发路线](docs/roadmap.md) 中的 Phase 1；完整任务与决策点见
[原始技术规划](docs/plans/v0.1-development-plan.zh-CN.md)。

仓库已于 2026-09-08 公开（早于原计划的 v0.1 时点）。**请始终假设你写的每一行内容最终都会公开**：
不提交凭据、客户数据、大模型文件或不明授权样本；commit 信息与注释不包含内部信息。

## 工程规则

### 测试

- 每个功能、修复和新 Adapter 必须在同一个 PR 内附带测试；没有测试的改动不接受合并。
- 单元测试覆盖 schema 验证、timestamp、adapter mapping、window buffer、事件生成和
  model manifest；集成测试覆盖 `fixture -> adapter -> runtime -> event` 路径。
- 每个 Adapter 保留小型固定 fixture（golden sample）；CI 永不下载完整数据集，
  也不依赖真实硬件；硬件测试标记 `pytest.mark.hardware` 并在 CI 中排除。
- 提交前必须全部通过：`ruff check`、`ruff format --check`、`mypy src`（strict）、
  `pytest -m "not hardware"`、`uv build`。CI 全绿是合并的必要条件。

### 注释与文档

- 每个模块的 docstring 说明该模块的 contract 与边界（现有 core 模块即此风格）。
- 公共 API 必须有英文 docstring；注释解释代码本身无法表达的约束，不复述代码。
- README 与文档必须诚实区分"已实现"与"预留 / 未实现"；示例数据必须标注 synthetic。
- 行为或接口决策记录到 docs/ADR/；API 在 v0.1 前保持实验性，v0.1 后变更需要 ADR。

### 语言约定

- 代码标识符、docstring、代码注释、commit 信息：英文。
- 文档（docs/、README.zh-CN.md）：当前中文，v0.1 前完成英文翻译。
- issue / PR 描述：中英文均可。

## 集成原则

- Core 保持轻量：厂商字段放 raw / metadata，重型依赖放未来的可选集成。
- 新 Adapter 需要小型合法 fixture、来源说明、时间戳规则和集成测试。

## 发布

PyPI 发布由 tag 触发的 CI 自动完成（Trusted Publishing，无 token）。
版本号升级、检查清单与故障排查见 [docs/release.zh-CN.md](docs/release.zh-CN.md)。
