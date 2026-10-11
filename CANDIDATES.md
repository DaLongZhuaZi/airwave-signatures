# 候选来源清单（2026-10-11 全网拓宽搜源的盘点结果）

本文件记录"已盘点、暂未进管线"的来源与结论，防止重复搜源。已进管线的来源见
`sources.yaml` 与 `SOURCES.md`。盘点方法：逐仓下载原始文件实测条数，结论均有出处；
找不到公开资料的明确标注，不臆测。

## 已评估：与现有目录重叠，无需重复接入

| 来源 | 结论 |
|---|---|
| Bluetooth-Devices/qingping-ble（FDCD 服务数据，18 个类型 ID） | Theengs 的清萍 fleet 已用同一 FDCD+类型字节路线覆盖，互为交叉验证，不重复建转换器 |
| Bluetooth-Devices 的 govee/inkbird/oralb/ruuvi/thermopro/mopeka/sensorpush/atc/xiaogui/leaone 等库 | 对应品牌 fleet 已由 Theengs 覆盖（Govee、Inkbird、Oral-B、Ruuvi、Mopeka、SensorPush 等逐个核对在目录中） |
| Moat S2（128 位服务数据 UUID） | **v101 文档误记为已覆盖，v102 核查纠正**：此前全目录无 Moat；其 128 位 UUID 服务数据规则形态与 SensorPush 先例一致，v102 已补手工 fleet |
| ThermoBeacon/Brifit 类型字节 0x14/0x30 | Theengs fleet 只收了 5 个类型，v102 已补手工 fleet（伪 companyId 口径与 Theengs 一致） |
| Kegtron | **最终裁定不可表达**：曾以为 companyId 0xFFFF + 固定 27 字节长度界可成 fleet，v102 构建时被校验器拦下——引擎要求 MANUFACTURER_DATA 必须带非空数据前缀，而 Kegtron 负载无任何恒定起始字节（字段直接排布）。除非引擎将来支持"cid+长度"规则，否则不收 |
| IEEE CID 注册表（221 条） | v101 时列为待定；v102 核查发现 bin 里原有 cid 段（218 条、来源未确认）就是这张表的旧快照且 App 本来就在读它作 24 位兜底——已改为官方 cid.csv 直接构建，App 零改动 |
| Google FMDN（FEAA+40/41） | 上游 v94 已有 "Google Find Hub" fleet 同规则覆盖 |
| Tile FEED+0200 前缀、Samsung FD5A | 上游 Tile/SmartTags fleet 已覆盖；FD69/FE33/FA25 为净增量（已进手工 fleet） |
| ble_monitor 的 xiaomi.py 设备表（77 条） | 与 xiaomi-ble 的 92 PID 同源同物，xiaomi-ble 已接入 |
| nmap-mac-prefixes（52085 条）/ hwdata oui.txt | 均为 IEEE 数据的再发布，对 radiodb 无增量 |
| Tasmota 模板库（blakadder/templates，2861 条） | 模板名是刷机后的用户侧名称、非出厂广播名，对名称规则无增量；可作产品-模组对照字典 |
| hexway/apple_bleee | GPL-3.0 且停更于 2023-10；其 Proximity 型号字表仅 4 条且过时（Bruce 的 27 条已接入），仅协议结构可参考 |

## 已评估：有真增量，待建转换器（按价值排序）

1. **custom-components/ble_monitor 独有品牌**（MIT）：**v102 已完成提取**——
   47 个品牌模块逐个深挖后，可表达的子集 21 个 fleet 已进管线（Teltonika/ELA、
   Michelin、Acconeer、AirMentor、Relsib、Mocreo、Chef iQ、Grundfos、Hörmann、
   Laica、Almendo、Blustream、Beckett、Jinou、ThermoPro、HolyIoT 追踪形态）；
   KKM/MikroTik/Oras/Sensirion/SmartDry 经实测已被 Theengs 覆盖。不可表达
   （引擎语义问题，非数据问题）：iNode（型号占 cid 高字节、低字节不校验）、
   Xiaogui（cid 高字节是帧计数器）、Sonoff（写死测试 MAC 门控 + XOR 加密）、
   AltBeacon（任意 cid + BEAC 前缀，规则必须绑单一 cid）、Beckett/Mocreo 的
   型号层（XOR 解包 / cid 高字节）。Senssun（cid 0x0100）碰撞风险高，主动不收。
   ThermoPro 此前被误以为已覆盖，实测 v101 目录无其设备 fleet，v102 已补名模式 fleet。
2. **SwitchBot 官方 BLE 规范**（OpenWonderLabs/SwitchBotAPI-BLE）：v102 已按官方
   类型码补齐缺口（WoButton/Hub/Hub Plus/Hub Mini/Fan/Curtain/Curtain 3/Lock/
   Meter 类型码 + 0969 协议级 fleet）；该仓无 LICENSE 文件，只取事实性类型码。
   余下未收：Contact/Motion 的配对模式码（0x44/0x53，常广播码已覆盖，价值低）。
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
