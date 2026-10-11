# 厂商 OUI fleet 审计记录

`vendors.json` 里每一条 org_patterns 都来自对 IEEE 官方注册表（MA-L 40319 /
MA-M 6628 / MA-S 7226，2026-10-11 实际下载）的逐厂商实验：先宽口径捞全部组织名，
再逐个核对、写出限定正则，并核对误命中名单。新增厂商必须先补做这套审计再进表。

## 收录口径

- 只用 MA-L 进 fleet；MA-M/MA-S 由 radiodb 厂商名查询覆盖。
- 误伤防范实例（均为实测）：`oppo` 须词边界（否则误中 Koppo/Toppower）；
  `vivo` 须全称（否则误中台湾监控商 Vivotek）；`gree` 须全称（否则 49 家 Green* 公司）；
  `mercury` 须带 COMMUNICATION（否则美国军工 Mercury Systems）；
  `fast` 须全称 SHENZHEN FAST TECHNOLOGIES；`dahua` 排除上海大华衡器厂；
  `lumi` 须全称 Lumi United Technology（否则近 40 家照明公司）；
  `imoo` 是子串陷阱（命中 Kiwimoore 芯存半导体），小天才改走母公司 BBK 教育电子。

## 拍板项（探针标 ⚠️ 的）

- **Lenovo / Motorola 拆两个 fleet**：161 条里 128 条组织名是 Motorola Mobility LLC,
  a Lenovo Company —— 产品品牌是 Motorola，合并会让用户看到的标签错误。
  实现：Lenovo 条目用 org_exclude_patterns 排除 motorola mobility。
- **Espressif / Quectel 收录为「模组商 fleet」**：命中只说明设备内含乐鑫/移远模组，
  fleet 名与 notes 均明示低特异性。Sonoff 等大量国产智能家居正是走乐鑫模组，
  这条 fleet 对国内场景的解释价值大于其误报面。
- **Anker 走备选实体 Fantasia Trading LLC**（6 条 MA-L，安克美国贸易主体）：
  Anker 在 IEEE 无自名条目（字面只命中 ANKER-EAST 圣彼得堡，无关）。
  fleet notes 已注明依据。
- **小天才走母公司 BBK EDUCATIONAL ELECTRONICS**（7 条）：命名为
  「Xiaotiancai / BBK」，notes 注明小天才/imoo 是步步高教育电子旗下品牌。
- **NIO 只收确定的 1 条**（NIO Co., Ltd.，MA-L）；另一条 San Jose 的 `Nio`（MA-M）
  登记质量可疑，不收。

## 不收录（OUI 路线不可用，均已实测）

- 组织名 0 命中：Ecovacs 科沃斯、Creality 创想三维、ITead/Sonoff、Ninebot 纳恩博、
  Unitree 宇树、XPeng、Li Auto（车和家）、Geely、Changan、Chery、SAIC Motor。
- 只有别家命中：Netcore 磊科（2 条均为台/美同名异家公司）、Great Wall
  （8 条全是中国电子长城计算机，与长城汽车无关）。
- 仅 MA-M/MA-S、无 MA-L：Bambu Lab 拓竹（Shenzhen Tuozhu，MA-M 1 条）、
  Orvibo 欧瑞博（MA-M 3 条）、Autel 道通（MA-M 2 条）——按 MA-L 口径不建 fleet，
  radiodb 仍可查名。

## 车企结论

整车厂普遍不以自己名义注册 OUI（模组由供应商注册）。新能源车识别应走 BLE
私有广播（companyId / service UUID / 名称）路线，不要在 OUI fleet 上投入。
