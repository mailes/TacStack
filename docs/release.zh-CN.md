# 发布流程（PyPI）

TacStack 通过 GitHub Actions + PyPI Trusted Publishing 自动发布，全程无 API
token。本文件是发版的操作手册与故障排查入口。

## 机制

- [.github/workflows/publish.yml](../.github/workflows/publish.yml)：推送
  `v*` tag 时触发，`uv build` 构建后由 `pypa/gh-action-pypi-publish` 通过
  GitHub OIDC 上传，无需任何密钥。
- PyPI 侧登记的 trusted publisher（Account Settings → Publishing）：
  project `tacstack` · owner `mailes` · repository `TacStack` · workflow
  `publish.yml` · environment `pypi`。**这五项必须与 workflow 文件及仓库
  严格一致，任何一项不匹配 OIDC 校验都会失败。**
- 首次发布 `v0.1.0a1`（2026-09-08）通过 pending publisher 完成项目认领，
  之后即为正式 trusted publisher。

## 发版步骤

1. **版本号两处同步升级**（当前为手动维护，改完用 `uv run tacstack version`
   核对）：
   - `pyproject.toml` 的 `version`
   - `src/tacstack/__init__.py` 的 `__version__`
2. `uv lock` 刷新锁文件（uv.lock 记录项目自身版本）。
3. 全部检查通过：

   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run mypy src
   uv run pytest -m "not hardware"
   uv build
   ```

4. 提交：`git commit -m "chore(release): vX.Y.Z"`。
5. 打 tag 并推送（tag 触发发布，main 与 tag 必须一起推）：

   ```bash
   git tag -a vX.Y.Z -m "TacStack vX.Y.Z"
   git push origin main vX.Y.Z
   ```

6. 约 1 分钟后 GitHub Actions 的 publish run 完成，产物自动上传。

## 版本号约定

- 遵循 PEP 440。当前处于 alpha 阶段：`0.1.0a1`、`0.1.0a2`、`0.1.0b1`……
- **预发布版 pip 默认不安装**：在 0.1.0 正式版发布前，用户需要
  `pip install --pre tacstack` 或 `pip install tacstack==0.1.0aX`。
  README 与官网 quickstart 中的 `--pre` 旗子在正式版发布后应移除。
- `0.1.0` 正式版对应 Phase 6（英文文档 + 外部用户 Quickstart）。

## 发布后验证

- GitHub Actions 的 publish run 为 success；
- `https://pypi.org/pypi/tacstack/json` 返回 200 且最新版本正确；
- 干净环境冒烟：`pip install --pre tacstack && tacstack version`。

## 注意事项

- **PyPI 上传后无法真正删除**（只能 yank 或放弃名字），发布前确认版本号、
  包描述与内容。
- 不要用本地 `uv publish` 绕过 CI：发布的产物必须与 git tag 一一对应。
- 改 workflow 文件名、environment 名、仓库名或 GitHub owner 前，先到 PyPI
  Account Settings → Publishing 同步更新 trusted publisher 登记，否则下次
  发布 OIDC 校验失败。
- CI 发布失败时，修正后**重新打同一个 tag**（`git tag -d vX.Y.Z &&
  git push origin :refs/tags/vX.Y.Z` 后重打）或直接重跑 Actions 里的
  publish workflow。
