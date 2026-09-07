# Core concepts

- SensorDescriptor：设备身份、坐标系名、标称频率、capabilities。
- TactileObservation：非负整数纳秒时间戳、raw、可选数组和质量元数据。
- TactileEvent：事件类型、模型身份、概率、latency；不等于已验证控制能力。
- CalibrationSpec：标定 id、所属设备、方法、参数。
- ModelManifest：模型身份、依赖能力、窗口长度、backend、artifact URI。

时间戳单位统一不代表时钟已经同步。Adapter 必须说明 device / host / episode 时钟来源；
跨流比较前需要显式对齐。事件 timestamp 表示输入事件时间，latency_ms 的测量边界
由具体 runtime 文档定义；Phase 0 尚无实际延迟测量。

数组的 shape、dtype、单位和坐标约定由具体 Adapter 明确记录，不能仅靠字段名推断。
probability 暂不保证跨模型校准。frozen dataclass 只禁止字段重新赋值，内部数组和 mapping
并非深度不可变。debug JSON 将数组变为列表，不能恢复 dtype / 原始二进制；未知对象报错，
不静默丢弃。raw 的持久化由后续存储集成负责。
