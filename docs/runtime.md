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
- 一个 Runtime 实例对应一个模型 × 一条流（事件状态机在模型实例内，不跨流共享）。

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

## ONNX（Phase 3 计划中）

计划：baseline 的打分计算导出为 ONNX 图（不引入 PyTorch），`runtime/onnx_backend.py`
提供 onnxruntime 推理后端，模型工件与 manifest 分离并启用 `artifact_uri` 字段，
ONNX 与 builtin 数值等价性进入测试。
