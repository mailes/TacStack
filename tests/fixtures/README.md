# Golden fixtures

Add small, license-compatible samples with each real adapter. Record source, license,
sensor, clock domain and expected outputs. CI must not download full datasets.
The current contract tests use explicitly synthetic arrays, not real tactile data.

## open_x_tactile/demo_wipe.tar

- 来源：由 `scripts/make_oxt_fixture.py` 生成（确定性，重跑字节一致）；内容 100%
  合成，不含任何真实数据集的像素或样本。
- 布局：镜像 FTP-1 发布 tar（HuggingFace `MJJJJ1064/FTP-1-Dataset` 的
  `VLA_touch.tar`）：`<Dataset>/<Task>.zarr`、zarr v2、`meta/episode_ends`、
  `data/*` time-major 数组、blosc/zstd 压缩；tar 成员顺序把点元数据文件放在
  chunk 之后（与真实 tar 观察到的乱序一致，用于验证读取不依赖成员顺序）。
- 数据形状故意用 32×32 而不是真实数据的 224×224，确保适配器不假设分辨率。
- 期望输出：3 个 episode（累计帧号边界 10 / 25 / 40），单触觉流
  `right_gripper`（GelSightMini，image，2 areas）。
- 时间域：帧序号（index domain），无 wall-clock。
- 真实数据抽查（手动，不进 CI）：2026-09-07 用 zarr 3.3 对照 `VLA_touch.tar`
  前 1 GB 验证了相同布局与压缩格式的读取（224×224×3 uint8 相机块与 `<U5`
  字符串数组解码正确；`Wipe_Manipulation.zarr` 61 episodes / 6421 帧）。
- 许可：合成内容，随 Apache-2.0 仓库分发无障碍。真实数据集的重分发需先确认
  许可（OXT 索引当前没有 license 字段）。
