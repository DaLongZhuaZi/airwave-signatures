#!/usr/bin/env python3
"""Apple Proximity Pairing 型号字 -> 分型号 fleet。

来源：Bruce 固件（GPL-3.0）的 APPLE_PROXIMITY_DEVICES 表（27 条，移植自
Flipper ble_spam 的 apple_devices，含 AirPods 4 / Pro 2 USB-C 等新款），
布局由 Flipper continuity.c 的报文构造代码实证：
Apple 厂商数据（companyId 0x004C，App 侧已剥公司 ID）中 Proximity Pairing
TLV = 07 19 <prefix> <model 大端 2 字节> …，prefix 0x01=已配对、0x07=新设备、
0x05=AirTag 类。Theengs 的现有 AirPods fleet 只有一条 071901 通用规则，
本转换器补齐型号级识别。
"""
import os
import re

DEVICE_RE = re.compile(r'\{\s*"([^"]+)",\s*0x([0-9A-Fa-f]{4})\s*\}')
AIRTAG_IDS = {0x0055, 0x0030}


def slug(name: str) -> str:
    s = name.lower().replace('+', '-plus')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'device'


def _rule(prefix_hex: str) -> dict:
    return {
        'kind': 'MANUFACTURER_DATA',
        'text': '',
        'companyId': 0x004C,
        'dataPrefixHex': prefix_hex,
        'radio': 'BLE',
        'enabled': True,
        'offset': 0,
    }


def convert(cache_dir: str):
    path = os.path.join(cache_dir, 'bruce-ble-spam.cpp')
    src = open(path, encoding='utf-8', errors='replace').read()
    start = src.find('APPLE_PROXIMITY_DEVICES[]')
    end = src.find('};', start)
    table = src[start:end] if start >= 0 else ''
    fleets = []
    seen = set()
    for name, hex_id in DEVICE_RE.findall(table):
        model = int(hex_id, 16)
        if model in seen:
            continue
        seen.add(model)
        model_hex = f'{model:04X}'
        prefixes = ['071905'] if model in AIRTAG_IDS else ['071901', '071907']
        rules = [_rule(p + model_hex) for p in prefixes]
        is_tag = model in AIRTAG_IDS
        if name.startswith(('Beats', 'Powerbeats', 'AirTag', 'Hermes', 'Apple')):
            display = name
        else:
            display = f'Apple {name}'
        fleets.append({
            'id': f'fleet-proximity-{slug(name)}',
            'name': display,
            'enabled': True,
            'matchAny': True,
            'colorIndex': 4,
            'rules': rules,
            'minPeers': 0,
            'peerWindowSec': 60,
            'clusterByOui': False,
            'sequentialMac': False,
            'notes': f'Apple Proximity Pairing model 0x{model_hex} in continuity TLV '
                     '(07 19, companyId 0x004C). Broadcast during pairing / case-open. '
                     'Source: Bruce firmware APPLE_PROXIMITY_DEVICES (GPL-3.0); '
                     'layout verified against Flipper continuity.c.',
            'attentionNote': '',
            'builtIn': True,
            'kind': 'FINDER' if is_tag else 'AUDIO',
        })
    return fleets, {'models': len(fleets)}
