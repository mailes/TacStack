# Adapter guide

实现 `tacstack.adapters.base.TactileAdapter`：descriptor / open / read / close。
`read()` 返回 Observation；离线数据结束抛 EOFError，其余设备或数据错误正常传播。

`observations(adapter)` 迭代已经打开的 Adapter，调用方使用 try/finally 负责 close。
实时超时、重连、时钟同步以及异步接口在接真实数据后确定。

新增实现时提供设备能力映射、时间来源、数组单位和 shape、样本来源及许可、固定 fixture。

## 已实现：open_x_tactile（Phase 1）

数据源是 Open-X-Tactile / FTP-1 发布的 tar 包（内含一个或多个 `<task>.zarr`，
zarr v2 格式，数据数组 blosc 压缩），或解包后的目录。要求本地 seekable 文件；
HTTP 流式读取不在 v0.1 范围。

- 任务与 episode：`meta/episode_ends`（int64 累计帧号）划分 episode；
  `data/*` 为 time-major 数组（首维 T = 总帧数）。
- 触觉流命名约定：`<side>_tactile_data_<group>` 及 `_sensor_ / _type_ / _area_`
  兄弟数组；`type=image` 映射到 `tactile_image`（GelSight 类，如 VLA_touch 的
  `right_tactile_data_gripper`），`type=state` 映射到 `taxels`（uSkin 类，如
  RH20TCfg7Tactile 的指尖触觉，真实形状为 (T, 2 areas, 16 taxels, 3 axes)）。
  两种负载用同一个 `for observation in adapter` 读取，schema 不偏向任何一种模态。
- RH20TCfg7Tactile 发布为分卷 tar（`*.tar.part-0000/0001/0002`）：按官方说明
  先拼接为单个 tar 再交给本适配器（`cat parts > full.tar`），适配器不感知分卷。
- 时间戳：FTP-1 的 `timestamps` 是帧序号（官方 parser 用 `arange` 合成），没有
  wall-clock 含义。适配器默认 `timestamp_domain="frame_index"`：
  `timestamp_ns = index * 1e9`（只保证单调可排序，不代表真实时间）；已知帧率时
  传 `rate_hz` 得到按帧率换算的 ns；对自带真实时间戳的数据集改用
  `timestamp_domain="nanoseconds"`。原始帧号始终保留在 `metadata["oxt_frame_index"]`。
- raw-first：每帧的小数组（关节、指令等）进 `raw`；相机等大体量非触觉流不逐帧
  拷贝，只在 `metadata["oxt_camera_streams"]` 记录名字，全精度数据保留在源数据集。
- 一个 Adapter 实例对应一个 (task, episode, tactile stream)；多流数据集必须显式
  指定 stream。

CLI：

```bash
uv run tacstack dataset list <tar-or-dir>
uv run tacstack dataset inspect <tar-or-dir> --task <task> --episode 0
uv run tacstack dataset convert <tar-or-dir> --task <task> --episode 0 --out demo.mcap
```

一个归档通常含多个 task（如 VLA_touch 内含 6 个 `<task>.zarr`），`list` 先看
清单；多 task 时 `inspect` / `convert` 必须传 `--task`。

MCAP 导出（`tacstack.integrations.mcap`）每帧写一条 JSON 消息（schema
`tacstack.tactile_observation.v1`），Foxglove 可直接打开；体量大的数组只写
shape / dtype / 统计摘要，全精度数据保留在源数据集中。

golden fixture 与真实布局的对应关系见 `tests/fixtures/README.md`。

## 仍为预留

mcap_replay / ros2 / real_sensor 目录当前没有可调用实现。
