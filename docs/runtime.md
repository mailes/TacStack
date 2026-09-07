# Model runtime

`TactileModel.manifest` 描述模型要求，`infer(window)` 接收 Observation 序列并返回事件列表。
ModelManifest.validate_capabilities 仅校验能力集合，不验证 shape、时钟、标定和模型效果。

后续执行链：window buffer → preprocessing → backend → threshold / event state machine。
Phase 3 计划使用 PyTorch 训练、ONNX 导出与 ONNX Runtime 推理，目前均未实现。
模型文件和 manifest 分离；模型标识、阈值、窗口和测量边界应进入评估记录。
