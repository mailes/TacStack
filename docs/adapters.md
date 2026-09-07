# Adapter guide

实现 `tacstack.adapters.base.TactileAdapter`：descriptor / open / read / close。
`read()` 返回 Observation；离线数据结束抛 EOFError，其余设备或数据错误正常传播。

`observations(adapter)` 迭代已经打开的 Adapter，调用方使用 try/finally 负责 close。
实时超时、重连、时钟同步以及异步接口在接真实数据后确定。

新增实现时提供设备能力映射、时间来源、数组单位和 shape、样本来源及许可、固定 fixture。
open_x_tactile / mcap / ros2 / real_sensor 目录当前均为预留，没有可调用实现。
