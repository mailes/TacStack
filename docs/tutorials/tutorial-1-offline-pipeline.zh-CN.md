# Tutorial 1：离线管线 —— 从数据集到触觉事件

全部命令离线可跑（使用仓库内置合成 fixture，不下载任何数据）；把
`tests/fixtures/open_x_tactile/demo_wipe.tar` 换成真实 OXT tar 即可处理真实数据。

前置：`uv sync`（Python 3.12+ 与 uv，见 README）。

## 1. 看一眼数据长什么样

```bash
uv run tacstack dataset list tests/fixtures/open_x_tactile/demo_wipe.tar
```

两个 task：`Wipe_Demo`（GelSightMini 图像流）与 `task_0001_Pick_Demo`
（uSkin matrix + ATIAxia80M20 力扭矩）。真实归档同样如此：先 `list` 再挑。

## 2. 健康检查

```bash
uv run tacstack dataset quality tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo
```

关注三件事：时间戳单调性（`timestamps.monotonic`）、步长统计
（`steps`，median 即帧间隔）、`suspected_gaps`（疑似丢帧）。接真实传感器后
这个命令就是健康检查的第一站。

## 3. 转成 MCAP（可被 Foxglove 打开）

```bash
uv run tacstack dataset convert tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --episode 0 --stream right_gripper \
    --calibration-id demo-cal --embed --out episode.mcap
```

`--embed` 把触觉数组全精度写进录制（体积换可回放性）；`--calibration-id`
记录标定溯源，随每一帧与事件贯通。

## 4. 跑 contact / slip baseline 出事件

```bash
uv run tacstack model run contact episode.mcap
uv run tacstack model run slip episode.mcap --slip-threshold 0.6
```

每行是一个 `TactileEvent` 的 debug JSON：`kind` / `probability` /
`latency_ms`（infer 墙钟时长）/ `model_id` / `metadata`（含活动值、阈值、
标定 id、源帧号）。`--out events.json` 可把全部事件存成 JSON 数组。

控制侧的等价 Python 代码只有三行：

```python
runtime = Runtime(builtin_model("contact"), window_frames=1)
for event in runtime.events(observations(adapter)):
    ...
```

完整可运行版本见 `examples/run_contact.py` 与 `examples/run_slip.py`。

## 5. 复现性验证

```bash
uv run tacstack benchmark contact tests/fixtures/open_x_tactile/demo_wipe.tar \
    --task Wipe_Demo --stream right_gripper --out report.json
```

同输入 + 同参数 ⇒ 事件流逐位一致（延迟为测量值，天然波动）。
`--all-streams` 会把 task 内每个触觉流各跑一遍并分组输出。

## 下一步

可视化与标注见 [Tutorial 2](tutorial-2-visualize-annotate.zh-CN.md)。
