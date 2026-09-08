# Tutorial 2：可视化与标注 —— Rerun 时间轴 + C/S/U 标记

前置：完成 [Tutorial 1](tutorial-1-offline-pipeline.zh-CN.md)；安装可选依赖
`uv sync --extra rerun --extra annotate`。

## 1. 一条命令的可视化回放

```bash
uv run tacstack demo --viewer
```

`demo` 在 `tacstack-demo/` 下生成 quality 报告、内嵌 MCAP、事件 JSON 和
`tactile.rrd`，并打开 Rerun viewer。也可以手动：

```bash
uv run tacstack replay tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --episode 1 --stream right_gripper \
    --extra-array camera_main_rgb --model slip --viewer
```

Viewer 里会有：

- **Images 行**：触觉图像 / taxel 热图 / 相机帧；
- **Series 行**：`events/slip`、`events/micro_slip` 曲线（`--model` 计算的
  事件概率，事件发生处出现数据点）、`raw/robot_joint/c0..` 等状态曲线；
- **Tensors & Text 行**：taxel 精确张量与指令文本；
- 顶部时间轴可在 `timestamp`（ns）与 `frame_index` 之间切换，拖动即逐帧检查。

## 2. 打标注

```bash
uv sync --extra annotate
uv run tacstack annotate add tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --episode 1 --stream right_gripper \
    --frame 6 --mark S --user mqh
uv run tacstack annotate show annotations.parquet
```

`--mark` 接受 C（contact）/ S（slip）/ U（unstable grasp）或全称；每行记录
episode 内帧号、绝对帧号、时间戳和标注人。

## 3. 标记重新加载到时间轴

```bash
uv run tacstack replay tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --episode 1 --stream right_gripper \
    --annotations annotations.parquet --viewer
```

匹配 task / episode / stream 的标记以 `annotations/<mark>` 文本落在对应时间
点上——人工排查 slip 时这就是"标记 → 重放 → 对齐"的闭环。

## 4. 也可以从 MCAP 回放

```bash
uv run tacstack dataset convert tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --episode 1 --stream right_gripper --embed --out episode.mcap
uv run tacstack replay episode.mcap --model slip --viewer
```

`.mcap` 录制是可移植的：发给别人，对方不需要原始数据集就能复现你的视图
（`model run` 同样接受 `.mcap` 源）。
