# Airwave Signatures / 电波足迹特征库

[电波足迹（Airwave Footprints）](https://github.com/DaLongZhuaZi/airwavefootprints) 的**独立特征数据仓库**：
负责收集、转换、校验和发布签名目录与厂商名称库，App 只消费本仓的发布产物，不再自己维护数据管线。

## 产物（`dist/`，格式与 App 现行契约完全一致）

| 文件 | 内容 | 消费方式 |
|---|---|---|
| `fieldwatch-signatures-v2.json` | 全量签名目录（`catalogVersion` 见 manifest） | App「特征库 → 更新内置目录」在线拉取；App 发版时钉一份快照进 rawfile 作离线首装 |
| `radiodb.bin` | IEEE / 蓝牙 SIG 名称库（SPLK 格式） | 随 App 发版分发（第二期加在线更新） |
| `cn-pack.json` | 仅国内相关新增/增补特征的可导入包 | 上游 Fieldwatch（Android）用户也可直接导入使用 |
| `manifest.json` | 版本、条数、各来源统计、SHA-256 | App 更新校验与人工核对 |

更新地址（raw）：`https://raw.githubusercontent.com/DaLongZhuaZi/airwave-signatures/main/dist/fieldwatch-signatures-v2.json`
镜像：`https://cdn.jsdelivr.net/gh/DaLongZhuaZi/airwave-signatures@main/dist/fieldwatch-signatures-v2.json`

## 数据来源与管线

来源清单、许可证与每项的角色见 [sources.yaml](sources.yaml) 与 [SOURCES.md](SOURCES.md)。
构建（Python 3 标准库，无第三方依赖）：

```sh
sh pipeline/build_all.sh   # 抓取 -> 合并构建 -> radiodb -> 校验
```

合并顺序是固定的，每一阶段都做 id/指纹去重与“被更宽规则覆盖”检查：

1. **上游 Fieldwatch 目录**全量透传（基底）；
2. **Theengs Decoder** 设备定义转换富化（`pipeline/converters/theengs.py`）；
3. **小米 MiBeacon 产品表**（HA 生态 xiaomi-ble 的 DEVICE_TYPES）→ `fleet-mibeacon-*`；
4. **IEEE 厂商 OUI**：为缺失的中国厂商新建 vendor fleet，并给大华/海康等过薄的已有 fleet 增补 OUI（`fleets/vendors.json`，匹配纪律见 `fleets/vendors.md`）；
5. **手工 fleet**（`fleets/manual/*.json`）：协议级与国内特化特征，每条必须注明指纹出处。

## 版本与发布纪律

- `catalogVersion` 由 `pipeline/VERSION` 单调递增管理（本仓纪元从 100 起），**不随上游版本号走**，避免出现“内置比更新源还新”的倒退；App 更新时会校验，只升不降。
- 自动更新（GitHub Actions 每周）只负责抓取+构建+校验并**开 PR**，发布必须人工看过 diff 报告后合并 —— 一条过宽的规则发出去就是所有用户一起误报。
- `radiodb.bin` 的 `cid` 段来源未明，只能从上一版原样保留（脚本会做新旧条数对比，丢失会报警）。

## 贡献国内特征

在 `fleets/manual/` 加一个 JSON 文件（一特征一文件），写清：名称模式 / companyId / service UUID / OUI 的**出处**
（官方文档、注册表、或你自己的抓包记录：设备型号 + 广播原文）。没有出处的不要提交 —— 宁可漏检，不可误报。

## License

本仓自有代码与手工数据为 MIT；合并产物中各来源数据的权利归属见 [SOURCES.md](SOURCES.md) 与 [NOTICE.md](NOTICE.md)。
