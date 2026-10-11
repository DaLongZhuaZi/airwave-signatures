#!/usr/bin/env python3
"""ble_monitor 独有品牌识别表 -> fleet。

来源：custom-components/ble_monitor（Ernst79，MIT）的 ble_parser 源码。
Theengs 已覆盖的品牌不在此列；本表（fleets/blemonitor.json）是 2026-10-11
逐个解析器人工提取的结果——ble_monitor 的识别逻辑是命令式代码（长度判定、
XOR 解包、cid 高字节……），能被规则引擎表达的子集才收，逐条出处见数据文件
与 SOURCES.md。表的手工刷新纪律见数据文件头注。
"""
import json
import os


def _rule(spec: dict) -> dict:
    rule = {
        'kind': spec['kind'],
        'text': spec.get('text', ''),
        'companyId': spec.get('companyId', 0),
        'dataPrefixHex': spec.get('dataPrefixHex', ''),
        'radio': 'BLE',
        'enabled': True,
    }
    for key in ('offset', 'group', 'minLen', 'maxLen'):
        if key in spec:
            rule[key] = spec[key]
    return rule


def convert(root: str):
    path = os.path.join(root, 'fleets', 'blemonitor.json')
    table = json.load(open(path, encoding='utf-8'))
    fleets = []
    for spec in table['fleets']:
        fleets.append({
            'id': spec['id'],
            'name': spec['name'],
            'enabled': True,
            'matchAny': True,
            'colorIndex': 4,
            'rules': [_rule(r) for r in spec['rules']],
            'minPeers': 0,
            'peerWindowSec': 60,
            'clusterByOui': False,
            'sequentialMac': False,
            'notes': spec['notes'],
            'attentionNote': '',
            'builtIn': True,
            'kind': spec['kind'],
        })
    return fleets, {'table_fleets': len(fleets)}
