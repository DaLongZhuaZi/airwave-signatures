# 候选来源清单（2026-10-11 全网拓宽搜源的盘点结果）

本文件记录"已盘点、暂未进管线"的来源与结论，防止重复搜源。已进管线的来源见
`sources.yaml` 与 `SOURCES.md`。盘点方法：逐仓下载原始文件实测条数，结论均有出处；
找不到公开资料的明确标注，不臆测。

## 已评估：与现有目录重叠，无需重复接入

| 来源 | 结论 |
|---|---|
| Bluetooth-Devices/qingping-ble（FDCD 服务数据，18 个类型 ID） | Theengs 的清萍 fleet 已用同一 FDCD+类型字节路线覆盖，互为交叉验证，不重复建转换器 |
| Bluetooth-Devices 的 govee/inkbird/oralb/ruuvi/thermopro/moat/mopeka/sensorpush/atc/thermobeacon/xiaogui/leaone 等库 | 对应品牌 fleet 已由 Theengs 覆盖（Govee、Inkbird、Oral-B、Ruuvi、Mopeka、SensorPush 等逐个核对在目录中）；moat 仅 1 型号且为非基 UUID 的 128 位服务数据，规则形态不稳，跳过 |
| Google FMDN（FEAA+40/41） | 上游 v94 已有 "Google Find Hub" fleet 同规则覆盖 |
| Tile FEED+0200 前缀、Samsung FD5A | 上游 Tile/SmartTags fleet 已覆盖；FD69/FE33/FA25 为净增量（已进手工 fleet） |
| ble_monitor 的 xiaomi.py 设备表（77 条） | 与 xiaomi-ble 的 92 PID 同源同物，xiaomi-ble 已接入 |
| nmap-mac-prefixes（52085 条）/ hwdata oui.txt | 均为 IEEE 数据的再发布，对 radiodb 无增量 |
| Tasmota 模板库（blakadder/templates，2861 条） | 模板名是刷机后的用户侧名称、非出厂广播名，对名称规则无增量；可作产品-模组对照字典 |
| hexway/apple_bleee | GPL-3.0 且停更于 2023-10；其 Proximity 型号字表仅 4 条且过时（Bruce 的 27 条已接入），仅协议结构可参考 |

## 已评估：有真增量，待建转换器（按价值排序）

1. **custom-components/ble_monitor 的独有品牌解析器**（MIT，ble_parser 47 个品牌模块）：
   Theengs 未覆盖的品牌包括 teltonika（资产追踪器）、mikrotik（标签）、michelin（胎压）、
   acconeer、chefiq、grundfos、holyiot、hormann、kkm、laica、mocreo、oras、relsib、
   sensirion、smartdry 等。各解析器多含设备字典，需逐个评估识别机制后写转换器。
2. **IEEE CID 注册表**（standards-oui.ieee.org/cid/cid.csv）：MA-L/M/S 之外的第四张
   IEEE 表，maclookup 的库里含它。注意 CID 用于本地管理位 MAC，是否并入 radiodb
   mal 段需先想清楚误报口径（随机 MAC 段），未定前不并入。
3. **SwitchBot 官方 BLE 规范**（OpenWonderLabs/SwitchBotAPI-BLE，10 个设备类型，
   service data 首字节为类型码）：Theengs 已有 7 个 SwitchBot fleet，本源可作官方
   校准与查漏；该仓无 LICENSE 文件，只取事实性类型码。
4. **BTHome object-id 细化**（Bluetooth-Devices/bthome-ble，95 个 object id）：
   可把现有协议级 BTHome fleet 细化到设备品类，依赖 App 引擎对 object id 的解析
   粒度，属二期。
5. **Samsung Buds 型号/颜色码全量**：现只用了 3 字节码的前两字节（第三字节被常量
   劈开）；若引擎将来支持多段前缀可细化到颜色款。

## 已评估：无公开资料 / 不可用（不要再找）

- 小牛 NIU、雅迪、爱玛的 BLE 广播规范：无公开资料（雅迪只有 App 层 Hook 研究）。
- 凯迪仕、德施曼智能锁 BLE：无公开资料（只有云端 HA 集成）。
- Reolink/Tapo/萤石的 BLE 配网广播名/UUID：社区仓库无记录。
- 无人机 Remote ID 厂商代码（CTA-2063）：GitHub 无公开结构化数据集；opendroneid
  只有协议编解码。无人机识别继续靠 OUI + 协议 fleet。
- Google Fast Pair 官方注册表：Google 不公开，社区表（已接入）是唯一现实来源。
- macvendors：只有 API、无批量下载；maclookup.app 可批量下载（含 CID 块）但
  再分发条款不明，不直接采用（正解是抓 IEEE CID 原始表，见上）。
- Verizon/Cube 追踪器在 AirGuard v2.2 无公开定义；Nut 已由 Theengs 覆盖。

## 已评估：范围外（记录备查）

- Zigbee herdsman-converters（5254 条设备定义，MIT，日更）：Zigbee 不在 App
  扫描范围内，仅作远期参考。
- DULT 统一防跟踪标准的声音服务 UUID：只出现在 GATT 连接后，不广播，被动
  扫描不可见（上游已有 DULT 协议 fleet FCB2）。
- FMDN 厂商/个体区分：ephemeral ID 每 1024 秒轮换，广播层只能识别到协议。
- 运动传感器品牌名模式（Magene/XOSS/迈金等）：行业通行做法是按标准型材
  （HR 180D/CSC 1816/功率 1818）识别，无公开的品牌名模式表；品类级 fleet
  已由上游的标准型材规则承担。
- SensorPro（T201/T301）：解析代码中 companyId 语义不清（MFR_IDS 集合与设备
  字节混杂），证据不足，暂不收。
- LED 灯带控制库（led-ble 等）：识别密度低（默认 model 字节泛化），不收。
