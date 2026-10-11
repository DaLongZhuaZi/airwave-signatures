#!/usr/bin/env python3
"""Google Fast Pair 型号 ID 表 -> FE2C 服务数据规则。

来源：Flipper Zero ble_spam 应用（Momentum-Apps，GPL-3.0）的 protocols/fastpair.c
——社区逆向汇编的 Fast Pair 型号注册表（Google 不公开官方注册表）。
识别机制：Fast Pair 广播的 service UUID 0xFE2C 服务数据前 3 字节（大端）即
Model ID，被动扫描可直接反查型号，与 SERVICE_DATA 规则天然对齐。

处理纪律：
- 源表里同一型号常有两种字节序各一条（历史包袱），按原样全收 —— 两种字节序
  在真实广播中都出现过，多收一条规则不误伤（3 字节 ID 空间足够稀疏）。
- 过滤明显的非产品条目（Test/Anti-Spoof/Foocorp/Dev Board 等源表自带的占位）。
- 按名称首词做品牌分 fleet；分不出的进通用 Fast Pair fleet。
"""
import os
import re

ENTRY_RE = re.compile(r'\{0x([0-9A-Fa-f]{1,6}),\s*"([^"]+)"\}')
JUNK_NAME = re.compile(r'^(test\b|anti-spoof|foocorp)|dev board|anti spoof', re.IGNORECASE)

# 名称首词/前缀 -> (fleet id 后缀, 显示名)。WH-/WF-/LinkBuds 是 Sony 的产品线命名。
BRAND_BY_TOKEN = {
    'jbl': ('jbl', 'JBL'),
    'sony': ('sony', 'Sony'),
    'lg': ('lg', 'LG'),
    'jabra': ('jabra', 'Jabra'),
    'bose': ('bose', 'Bose'),
    'google': ('google', 'Google'),
    'pixel': ('google', 'Google'),
    'galaxy': ('samsung', 'Samsung'),
    'samsung': ('samsung', 'Samsung'),
    'soundcore': ('soundcore', 'Soundcore'),
    'beoplay': ('bang-olufsen', 'Bang & Olufsen'),
    'b&o': ('bang-olufsen', 'Bang & Olufsen'),
    'realme': ('realme', 'Realme'),
    'boat': ('boat', 'boAt'),
    'oraimo': ('oraimo', 'Oraimo'),
    'cleer': ('cleer', 'Cleer'),
    'linkbuds': ('sony', 'Sony'),
}
SONY_MODEL_PREFIX = ('WH-', 'WF-', 'WI-', 'MDR-', 'SRS-', 'ULT ')


def brand_of(name: str):
    token = name.split(' ')[0].lower()
    if token in BRAND_BY_TOKEN:
        return BRAND_BY_TOKEN[token]
    if any(name.startswith(p) for p in SONY_MODEL_PREFIX):
        return BRAND_BY_TOKEN['sony']
    return ('generic', 'Google Fast Pair')


def _rule(model_hex: str) -> dict:
    return {
        'kind': 'SERVICE_DATA',
        'text': 'FE2C',
        'companyId': 0,
        'dataPrefixHex': model_hex.upper(),
        'radio': 'BLE',
        'enabled': True,
        'offset': 0,
    }


def _fleet(suffix: str, brand: str, rules: list, sample_names: list) -> dict:
    return {
        'id': f'fleet-fastpair-{suffix}',
        'name': f'{brand} (Fast Pair)',
        'enabled': True,
        'matchAny': True,
        'colorIndex': 4,
        'rules': rules,
        'minPeers': 0,
        'peerWindowSec': 60,
        'clusterByOui': False,
        'sequentialMac': False,
        'notes': 'Google Fast Pair model ID in FE2C service data (first 3 bytes, big-endian). '
                 f'Models include: {", ".join(sample_names[:6])}. '
                 'Source: Flipper ble_spam fastpair.c community registry (GPL-3.0), '
                 'cross-checked against DiamondRoPlayz/FastPair-Models.',
        'attentionNote': '',
        'builtIn': True,
        'kind': 'AUDIO',
    }


def convert(cache_dir: str):
    path = os.path.join(cache_dir, 'fastpair.c')
    src = open(path, encoding='utf-8', errors='replace').read()
    by_brand: dict[str, dict] = {}
    seen_values: set[int] = set()
    total = 0
    skipped_junk = 0
    for hex_value, name in ENTRY_RE.findall(src):
        value = int(hex_value, 16)
        if value in seen_values:
            continue
        seen_values.add(value)
        if JUNK_NAME.search(name):
            skipped_junk += 1
            continue
        suffix, brand = brand_of(name)
        bucket = by_brand.setdefault(suffix, {'brand': brand, 'rules': [], 'names': []})
        bucket['rules'].append(_rule(f'{value:06X}'))
        bucket['names'].append(name)
        total += 1
    fleets = []
    for suffix, bucket in sorted(by_brand.items()):
        fleets.append(_fleet(suffix, bucket['brand'], bucket['rules'], bucket['names']))
    stats = {
        'model_ids': total,
        'skipped_junk': skipped_junk,
        'brand_fleets': {k: len(v['rules']) for k, v in sorted(by_brand.items())},
    }
    return fleets, stats
