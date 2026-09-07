# Golden fixtures

Add small, license-compatible samples with each real adapter. Record source, license,
sensor, clock domain and expected outputs. CI must not download full datasets.
The current contract tests use explicitly synthetic arrays, not real tactile data.

## open_x_tactile/demo_wipe.tar

- 来源：由 `scripts/make_oxt_fixture.py` 生成（确定性，重跑字节一致）；内容 100%
  合成，不含任何真实数据集的像素或样本。
- 布局：镜像 FTP-1 发布 tar（HuggingFace `MJJJJ1064/FTP-1-Dataset`，如
  `VLA_touch.tar`）：单个 tar 内含多个 `<Task>.zarr`、zarr v2、
  `meta/episode_ends`、`data/*` time-major 数组、blosc/zstd 压缩；tar 成员顺序
  把点元数据文件放在 chunk 之后（与真实 tar 观察到的乱序一致，用于验证读取不
  依赖成员顺序）。
- 数据形状故意用 32×32 而不是真实数据的 224×224，确保适配器不假设分辨率。

### Wipe_Demo（图像流，镜像 VLA_touch / GelSightMini 布局）

- 流：`right_gripper`（GelSightMini，type=image，2 areas，(T, 2, 32, 32, 3) uint8）。
- 3 个 episode（累计帧号边界 10 / 25 / 40）。

### task_0001_Pick_Demo（taxel 流，镜像 RH20TCfg7Tactile 布局）

- 镜像真实 task `task_0050_Dish_on_rack` 的数组清单（数组元数据与
  sensor/type 字符串均已对照发布 tar 验证）：两个触觉流 —— `right_gripper`
  （uSkin，type=**matrix**，(T, 2, 4, 4, 3) float32，对应 RH20T 官方文档的
  2 指尖 × 4×4 taxel × 3 轴）与 `right_grippertorque`（ATIAxia80M20 六轴
  力扭矩，type=state，(T, 1, 6)）；另有 `right_hand_pose (T,1,6)`、
  `right_wrist_pose (T,6)`、`robot_joint (T,21)`、`robot_ft_base (T,6)`、
  `gripper_width_m`、两路 224 类相机与 `sub_task_instruction`（fixture 相机
  分辨率仍为 32×32）。
- 2 个 episode（累计帧号边界 8 / 20）；task 内多流，回放需显式指定 stream。

### 通用

- 时间域：帧序号（index domain），无 wall-clock。
- 真实数据抽查（手动，不进 CI）：2026-09-07 用 zarr 3.3 对照 `VLA_touch.tar`
  前 1 GB 验证了相同布局与压缩格式的读取（224×224×3 uint8 相机块与 `<U5`
  字符串数组解码正确；`Wipe_Manipulation.zarr` 61 episodes / 6421 帧）；同日
  通过对 `RH20TCfg7Tactile.tar.part-0000` 的 tar 头部遍历确认了
  `task_0050_Dish_on_rack` 的完整数组清单（上节列出的键名、形状、dtype 与
  blosc/zstd 压缩全部来自该遍历）。
- 许可：合成内容，随 Apache-2.0 仓库分发无障碍。真实数据集的重分发需先确认
  许可（OXT 索引当前没有 license 字段）。
