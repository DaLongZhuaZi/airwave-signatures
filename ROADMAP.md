# ROADMAP

## 第二期（已明确要做）

- **radiodb.bin 在线更新**：App 侧目前只能随包分发；数据仓侧已具备周更能力，
  待 App 加一条与签名目录同级的更新通道（版本校验 + 镜像回退）。
- **SwitchBot 等 HA 生态 BLE 库**：Bluetooth-Devices 组织下还有一批设备解析库
  （xiaomi-ble 已接入）；逐个评估其产品表能否映射到现有规则形态。
- **BTHome 设备细化**：BTHome 是开放规范、设备自报 object id，现只有协议级
  fleet；可按 object id 组合细化到品类（温湿度/门磁/人体等）。

## 待调研（无可靠来源前不做）

- **运营商网关默认 SSID 模式 fleet**（CMCC-/ChinaNet-/CU_ 前缀）：没有成文的可信
  模式表；网关 OEM 的 OUI fleet（烽火/中兴/创维/华为）已先行覆盖识别。
- **新能源车 BLE 私有广播**：车企无 IEEE OUI 可用，须从车主社区/抓包整理
  companyId/UUID/名称模式，每条都要有出处才收。
- **Ecovacs / Sonoff / Ninebot / Unitree 等 OUI 零命中厂商**：同上，走名称/BLE 路线，
  找到可靠指纹来源再建手工 fleet。
- **Theengs 不可表达的 17 台**：嵌套括号条件、否定判定（not_/no-mfgdata）、
  半字节片段与 `<` 长度比较——需要引擎侧先支持新语义，数据仓不 hack 绕过。

## 纪律（长期有效）

- 无出处的特征不入库；过宽规则宁可不发。
- 自动周更只开 PR，人工看 diff 后才合并发布。
- radiodb 的 cid 段在查清来源前只许原样保留 + 条数对比报警。
