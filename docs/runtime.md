# Model runtime

## Contract

`TactileModel.manifest` 描述模型要求，`infer(window)` 接收 Observation 序列并返回事件列表。
ModelManifest.validate_capabilities 仅校验能力集合，不验证 shape、时钟、标定和模型效果。

## 已实现：Runtime 事件循环（Phase 3）

`tacstack.runtime.pipeline.Runtime` 把 adapter → WindowBuffer → model 串成事件流：

```python
from tacstack.adapters.base import observations
from tacstack.models import builtin_model
from tacstack.runtime.pipeline import Runtime

model = builtin_model("slip", micro_threshold=0.4)
runtime = Runtime(model, window_frames=2)
for event in runtime.events(observations(adapter)):
    if event.kind == "slip":
        ...
```

- 窗口以帧为单位（index domain 没有真实时钟；manifest 的 `window_ms` 是模型级声明，
  已知帧率时按 `ceil(window_ms / 1000 * rate_hz)` 推导帧数）；
- 事件上的 `latency_ms` 是产出它的 `infer` 调用的墙钟时长（模型自测，Runtime 以同一
  测量重新标注，调用方只有一个定义）；
- 一个 Runtime 实例对应一个模型 × 一条流（事件状态机在模型实例内，不跨流共享）；
- capability 校验在每条流的首帧执行，两级语义：`manifest.required_capabilities`
  为 **all-of**（逐项必须具备）；模型可选的 `accepted_capabilities` 为 **any-of**
  （与传感器能力至少相交一项）。内置与 ONNX 模型均声明
  `{tactile_image, taxel_force}`。

## 已实现：内置 baseline 模型

- `contact-baseline`：逐帧 activity（payload 幅值均值，uint8 图像归一化到 [0,1]）→
  logistic 概率 → 迟滞状态机，边沿触发 `contact_begin` / `contact_end`；
- `slip-baseline`：帧间平均绝对差 → logistic 分数 → 上升沿触发 `micro_slip` / `slip`
  （持续 slip 只发一次，分数回落后再次上升会重新触发）；需要 `window_frames >= 2`；
- 两者都是**确定性启发式**，不是学习模型；默认参数未做跨传感器标定（Phase 4 处理）；
  对无法提供触觉 payload 的流会显式抛错；
- `builtin_model("contact" | "slip", **params)` 工厂；阈值 / center / gain 可在构造或
  CLI 覆盖。

## CLI

```bash
uv run tacstack model run contact <tar> --task <task> --episode 0 --stream <stream> \
    [--on-threshold 0.6 --off-threshold 0.4] [--out events.json]
uv run tacstack benchmark slip <tar> --task <task> --out report.json
```

benchmark 跑遍 task 的所有 episode（每个 episode 重建 Runtime 保证状态独立），报告含
逐 episode 帧数 / 事件计数（按 kind 分组）/ 延迟统计。可复现契约：同输入 + 同参数 ⇒
事件流（kind / probability / 顺序）逐位一致；延迟是测量值，天然随运行波动。

## 已实现：ONNX 打分工件 + onnxruntime 后端（Phase 3）

baseline 的打分部分（幅值均值 / 帧间绝对差 → logistic）导出为手写 ONNX 图
（opset 17，不引入 PyTorch），center/gain 固化为图内 initializer。工件输入是
**幅值帧展平后的 float32 向量**，与 payload 形状无关；事件状态机
（`ContactHysteresis` / `SlipEdgeTracker`）与 builtin 共享——同一分数序列下两者
输出完全相同的事件序列（等价性测试 abs 1e-5，覆盖 float32 vs float64 差异）。

```python
from tacstack.runtime.onnx_backend import OnnxContactModel, export_contact_scoring

artifact = export_contact_scoring("contact.onnx")  # 也可用外部导出的 .onnx
model = OnnxContactModel(artifact, on_threshold=0.6)
runtime = Runtime(model, window_frames=1)
```

CLI：`model run` / `benchmark` 传 `--artifact model.onnx [--model-id contact-onnx]`
即切换到 onnxruntime 后端；`center/gain` 在导出时固化，不再从 CLI 接受。
manifest 记录 `runtime="onnxruntime"` 与 `artifact_uri`（工件与 manifest 分离）。
依赖：`uv sync --extra onnx`（`onnx` 用于导出，`onnxruntime` 用于推理）。
