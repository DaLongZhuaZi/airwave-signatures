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
- `cid` 段：IEEE CID 注册表（standards-oui.ieee.org/cid/cid.csv，221 条）。v101 之前
  此段来源未确认、从旧 bin 保留；2026-10-11 核查确认旧段（218 条）就是这张表的旧
  快照（量级吻合、App 本来就在读它作 MA-L 之后的 24 位兜底查询），v102 起改用官方
  表直接构建，抓取失败才回退旧 bin 保留。
- 显示名覆盖仅两条（FE95 → Xiaomi Mi Service (MiBeacon)、FCD2 → BTHome）：
  SIG 成员表里只有公司名，设备详情里显示协议名才有辨识价值；只改名、不增条目。

## 6. 社区逆向汇编的配对/型号表（v101 新增）

这一类来源的共性：数据本身是各厂商广播里的**事实性编码表**（型号 ID、型号字节），
由社区从真实设备广播逆向汇编，维护活跃；转换器只做格式映射，不做任何推测填充。

- **Flipper ble_spam fastpair.c**（Momentum-Apps，GPL-3.0）：Google 不公开 Fast Pair
  型号注册表，社区表 530 条（过滤测试/占位条目后 490 条进目录），FE2C 服务数据前
  3 字节即型号 ID。按品牌分 fleet（Sony 135、JBL 88、LG 27 为大头），分不出的进
  通用 Fast Pair fleet；与 DiamondRoPlayz/FastPair-Models（122 条）交叉核对过。
- **Flipper ble_spam easysetup.c**（同上）：三星 EasySetup 配对广播
  （companyId 0x0075）。Watch 型号字节位于固定头 `010002000101FF000043` 之后，
  按"去颜色词后的型号名"分 fleet（Watch4/5/6 各尺寸）；Buds 的 3 字节型号/颜色码
  被常量字节劈开，只取前两字节做前缀（20 条）。
- **Bruce 固件 APPLE_PROXIMITY_DEVICES**（GPL-3.0，移植自 Flipper 且更新）：Apple
  Proximity Pairing 型号字 27 条（07 19 TLV + 状态前缀 01/07，AirTag 类为 05），
  逐型号建 fleet —— Theengs 的 AirPods fleet 只有一条通用规则，型号级识别由此补齐。
- **bluemaestro-ble**（Bluetooth-Devices，MIT）：companyId 0x0133 + 首字节类型 ID，
  8 个类型（含 THD 的 legacy/现行双 ID 合并为一个 fleet）。

## 7. ble_monitor 独有品牌 + SwitchBot 官方校准（v102 新增）

- **ble_monitor**（Ernst79，MIT）：HA 社区的老牌 BLE 监控组件，47 个品牌解析器与
  Theengs 大面积重叠，但有十几个独有品牌。其识别逻辑是命令式 Python（长度判定、
  链式 XOR 解包、把型号字节藏进 company ID 高字节等），无法逐文件自动转换；
  2026-10-11 逐个解析器人工提取了**可被规则引擎表达**的子集（Teltonika/ELA、
  Michelin 胎压、Acconeer、AirMentor、Relsib、Mocreo、Chef iQ、Grundfos、Hörmann、
  Laica、Almendo、Blustream、Beckett、Jinou、ThermoPro 名模式、HolyIoT 追踪形态，
  共 21 个 fleet），落成 `fleets/blemonitor.json` 数据表 + 转换器。不可表达的
  （iNode、Xiaogui、Sonoff、AltBeacon、Beckett 型号层、Mocreo 型号层）与主动
  不收的（Senssun，cid 0x0100 碰撞风险）理由见 CANDIDATES.md。
- **SwitchBot 官方规范**（OpenWonderLabs/SwitchBotAPI-BLE，无许可证文件，只取
  事实性类型码）：按官方 FD3D 类型码逐项核对 Theengs 的 7 个 fleet，补齐缺口
  10 个手工 fleet（WoButton、Hub、Hub Plus、Hub Mini、Fan、Curtain、Curtain 3、
  Lock、Meter 类型码、0969 协议级）。Color Bulb/LED Strip/Plug Mini 官方广播无
  类型字节，只能靠 0x0969 厂商数据整体识别到品牌。

## 8. 手工 fleet

`fleets/manual/*.json`：协议级（MiBeacon 通用、BTHome、Eddystone）与国内特化特征。
入库门槛：文件内 `notes` 必须写明指纹出处。无出处的"听说"不收。
v101 拓宽搜源后新增的手工 fleet 及其出处：三星离线查找 FD69 / Chipolo FE33 /
Pebblebee FA25（seemoo-lab/AirGuard，Apache-2.0，且与 SIG 成员注册表对 FD69/FE33
的归属互相印证）、Ninebot/小米滑板车（社区协议文档）、TTLock 0x1910
（ttlock-ble，MIT）、Meross（厂商组织仓 meross_rpc 的 HA 发现口径，MIT）、
云麦/Picooc/QN 体重秤名模式（openScale handlers，GPL-3.0，事实性名模式）、
Coospo 码表、Tilt 酿造比重计 iBeacon UUID（tilt-ble，MIT）。
盘点过但未采用的来源与理由见 `CANDIDATES.md`。
