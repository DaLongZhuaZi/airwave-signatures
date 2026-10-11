# 数据来源与处理说明

本仓产出的每一条特征都能追溯到这里列出的来源。机器可读清单在 `sources.yaml`，
构建统计（每来源实际贡献多少）随每次发布写进 `dist/manifest.json` 的 `sources` 段。

## 1. 上游 Fieldwatch 目录（基底）

- 来源：OffGridPete/Fieldwatch（Android，MIT）的 `dist/fieldwatch-signatures-v2.json`。
- 处理：全量透传，不改任何一条规则；其后的所有阶段只做**新增/增补**，不删改上游行
  （增补只发生在第 4 阶段给指定 fleet 追加 OUI 规则，manifest 里逐 fleet 记录条数）。
- 已知局限：美国现场视角（ISP/执法/监控类最全），这正是本仓存在的理由。

## 2. Theengs Decoder（BLE 传感器/信标）

- 来源：theengs/decoder 的 `src/devices/*.h`（每文件内嵌设备 JSON）。
- 转换：`pipeline/converters/theengs.py`（基底源自 airwavefootprints 的
  `scripts/fieldwatch-data/build-catalog.py`，本仓做了四处修复）：
  1. 一个文件含多个设备 JSON 时全取（原实现只取第一个，tracker 等整组丢失）；
  2. `name` 条件是字面名称而非 hex（原实现校验失败整台丢弃，Nut 等追踪器因此缺失）；
  3. `uuid contain <厂商UUID>` 放行（原被黑名单误杀，Mi Band/Amazfit 的 FEE0 因此缺失）；
  4. 纯长度段不再误作数据前缀；主条件不可表达时回退 `conditionnomac`。
- 仍然不可表达（引擎语义所限，跳过并计数）：`mac@index`（个体 MAC，本就不该做 fleet）、
  `no-mfgdata` / `not_`（否定判定）、嵌套括号条件、奇数位 hex 与 `<` 长度比较。
- 精度守卫：单条 SIG 采纳服务 UUID（如 0x180F 电池服务）不构成身份，丢弃；
  厂商自定义 UUID（FEE0/FE95/FCD2 等）本身即协议标识，允许单条成 fleet。
  另有“弱片段守卫”：OR 组只剩无公司 ID 的短厂商数据片段时整台跳过，防大面积误报。
- 与原转换器的基线 diff（上游 v94 为基底，发布前实测）：原产出 313 条 fleet 中
  312 条在本仓保留，其中 309 条规则逐条不变；3 条（Feasycom、MiFlora JCY01、
  NodOn NIU）修正了同一类误译 —— 纯长度段（如 `servicedata = 22`）曾被当成
  数据前缀 `"22"`，修正后长度约束回归本义；1 条（HHCCJCY10）修正后只剩
  SERVICE_UUID FD50 单规则，被上游 Tuya fleet 的同名规则覆盖而跳过
  （FD50 实为 HHCC 服务，上游 Tuya 占用它属上游存量行为，本仓不改上游行）。

## 3. 小米 MiBeacon 产品表

- 来源：Bluetooth-Devices/xiaomi-ble（Home Assistant 官方生态解析库，MIT）的
  `DEVICE_TYPES`（product_id → 名称/型号/制造商）。
- 结构依据：该库 parser 实证 MiBeacon 负载 = 帧控制(2B) + product_id(2B 小端) + …；
  App 解析时服务数据已剥 UUID，故规则为 `SERVICE_DATA text=FE95 offset=2 prefix=<PID 小端 hex>`。
- 同型号多 PID 合并为一个 fleet；解析用 Python `ast`，不执行抓回的代码。

## 4. IEEE 注册表（MA-L）与厂商 fleet

- 来源：IEEE MA-L 公开注册表（`oui.csv`）。
- 只用 MA-L 进签名 fleet（与上游惯例一致）；MA-M/MA-S 长前缀由 radiodb 的厂商名查询覆盖。
- 厂商组织名匹配表在 `fleets/vendors.json`，逐厂商的命中组织名与消歧审计在
  `fleets/vendors.md` —— 新增厂商必须先在那里留下审计记录。

## 5. radiodb.bin 的四方来源

- MA-L / MA-M / MA-S：IEEE 官方 CSV。
- 公司 ID、GAP Appearance、服务 UUID：Bluetooth SIG Assigned Numbers
  （`company_identifiers.yaml` / `appearance_values.yaml` / `service_uuids.yaml` /
  **`member_uuids.yaml`**）。原版漏了成员 UUID 表，导致 uuid 段只有 84 条、
  FE95（小米）等查不到名；本仓补上。
- Nordic bluetooth-numbers-database（BSD-3）：SIG 两表之后并入补漏，命名以 SIG 为准。
- `cid` 段：来源未确认，只能从上一版 bin 原样保留，脚本会报告新旧条数差。
- 显示名覆盖仅两条（FE95 → Xiaomi Mi Service (MiBeacon)、FCD2 → BTHome）：
  SIG 成员表里只有公司名，设备详情里显示协议名才有辨识价值；只改名、不增条目。

## 6. 手工 fleet

`fleets/manual/*.json`：协议级（MiBeacon 通用、BTHome、Eddystone）与国内特化特征。
入库门槛：文件内 `notes` 必须写明指纹出处。无出处的“听说”不收。
