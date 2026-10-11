#!/usr/bin/env python3
"""BlueMaestro Tempo Disc 环境记录仪 -> 分型号 fleet。

来源：Bluetooth-Devices/bluemaestro-ble（MIT）的 parser.py：
companyId 0x0133，厂商数据首字节（App 侧已剥公司 ID，offset 0）为设备类型 ID。
注：0x0133 并非 BlueMaestro 在 SIG 的注册值（ThermoPro 等也在用），但类型字节
组合足够特异；规则带完整类型字节前缀，不会与 ThermoPro 的 33 01 开头数据混淆。
"""
import os
import re

CONST_RE = re.compile(r'^([A-Z0-9_]+_ID)\s*=\s*0x([0-9A-Fa-f]+)', re.MULTILINE)
ENTRY_RE = re.compile(r'([A-Z0-9_]+_ID):\s*BlueMaestroDevice\(\s*"([^"]+)"')
VAR_RE = re.compile(r'^(_\w+)\s*=\s*BlueMaestroDevice\(\s*"([^"]+)"', re.MULTILINE)
ENTRY_VAR_RE = re.compile(r'([A-Z0-9_]+_ID):\s*(_\w+)\b')


def _rule(type_hex: str) -> dict:
    return {
        'kind': 'MANUFACTURER_DATA',
        'text': '',
        'companyId': 0x0133,
        'dataPrefixHex': type_hex,
        'radio': 'BLE',
        'enabled': True,
        'offset': 0,
    }


def slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'device'


def convert(cache_dir: str):
    path = os.path.join(cache_dir, 'bluemaestro-parser.py')
    src = open(path, encoding='utf-8', errors='replace').read()
    consts = {name: int(value, 16) for name, value in CONST_RE.findall(src)}
    entries = dict(ENTRY_RE.findall(src))
    var_names = dict(VAR_RE.findall(src))
    for const_name, var in ENTRY_VAR_RE.findall(src):
        if var in var_names:
            entries.setdefault(const_name, var_names[var])
    # 同一设备可能有多个类型 ID（如 THD 的 legacy 0x16 与现行 0x17 同指一个型号）
    by_device: dict[str, list[int]] = {}
    for const_name, device_name in entries.items():
        type_id = consts.get(const_name)
        if type_id is not None:
            by_device.setdefault(device_name, []).append(type_id)
    fleets = []
    for device_name, type_ids in by_device.items():
        display = device_name if device_name.startswith('BlueMaestro') else f'BlueMaestro {device_name}'
        fleets.append({
            'id': f'fleet-bluemaestro-{slug(device_name)}',
            'name': display,
            'enabled': True,
            'matchAny': True,
            'colorIndex': 4,
            'rules': [_rule(f'{t:02X}') for t in sorted(type_ids)],
            'minPeers': 0,
            'peerWindowSec': 60,
            'clusterByOui': False,
            'sequentialMac': False,
            'notes': 'BlueMaestro manufacturer data (companyId 0x0133), device type byte(s) '
                     f'{", ".join(f"0x{t:02X}" for t in sorted(type_ids))} at payload offset 0. '
                     'Source: Bluetooth-Devices/bluemaestro-ble (MIT).',
            'attentionNote': '',
            'builtIn': True,
            'kind': 'HOME',
        })
    return fleets, {'models': len(fleets)}
