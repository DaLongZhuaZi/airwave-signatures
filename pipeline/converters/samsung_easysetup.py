#!/usr/bin/env python3
"""Samsung EasySetup 配对广播 -> Galaxy Watch / Buds fleet。

来源：Flipper Zero ble_spam（Momentum-Apps，GPL-3.0）protocols/easysetup.c，
布局由其报文构造代码实证（companyId 0x0075，App 侧已剥公司 ID）：
- Watch：负载 = 01 00 02 00 01 01 FF 00 00 43 <model 1 字节>，源表 48 个型号字节
  （无名称，只有代码，故只做协议级 fleet 并在 notes 里声明）。
- Buds：负载 = 42 09 81 02 14 15 03 21 01 09 <hi> <mid> 01 <lo> …，型号/颜色
  3 字节码被常量字节劈开，只能用前 12 字节（含 hi/mid 两字节）做前缀；
  同 (hi,mid) 的颜色变体合并，名称列进 notes。
设备仅在配对/EasySetup 流程中发这类广播，命中即"附近有人在配对三星穿戴"。
"""
import os
import re

WATCH_PREFIX = '010002000101FF000043'
BUDS_PREFIX = '42098102141503210109'


def _mfr_rule(prefix_hex: str) -> dict:
    return {
        'kind': 'MANUFACTURER_DATA',
        'text': '',
        'companyId': 0x0075,
        'dataPrefixHex': prefix_hex,
        'radio': 'BLE',
        'enabled': True,
        'offset': 0,
    }


def _fleet(fid: str, name: str, kind: str, rules: list, notes: str) -> dict:
    return {
        'id': fid,
        'name': name,
        'enabled': True,
        'matchAny': True,
        'colorIndex': 4,
        'rules': rules,
        'minPeers': 0,
        'peerWindowSec': 60,
        'clusterByOui': False,
        'sequentialMac': False,
        'notes': notes,
        'attentionNote': '',
        'builtIn': True,
        'kind': kind,
    }


def convert(cache_dir: str):
    path = os.path.join(cache_dir, 'easysetup.c')
    src = open(path, encoding='utf-8', errors='replace').read()
    fleets = []

    def block(marker: str) -> str:
        start = src.find(marker)
        if start < 0:
            return ''
        end = src.find('};', start)
        return src[start:end] if end > start else ''

    watch_block = block('watch_models[]')
    watch_entries = re.findall(r'\{0x([0-9A-Fa-f]{2}),\s*"([^"]+)"\}', watch_block)
    colors = {'white', 'black', 'silver', 'green', 'pink', 'blue', 'gold', 'gray',
              'grey', 'bronze', 'purple', 'cream', 'lavender', 'graphite', 'olive',
              'fox', 'french', 'purpleish', 'sapphire', 'cyan', 'beige', 'brown',
              'red', 'violet', 'mint', 'ivory', 'khaki', 'navy', 'coral', 'teal',
              'burgundy', 'champagne', 'titanium', '&', 'and'}
    watch_groups: dict[str, list[int]] = {}
    watch_fallback: list[int] = []
    for hex_byte, raw_name in watch_entries:
        byte = int(hex_byte, 16)
        name = raw_name.strip()
        if name.lower().startswith('fallback'):
            watch_fallback.append(byte)
            continue
        words = name.split(' ')
        while len(words) > 1 and words[0].lower() in colors:
            words = words[1:]
        # 中间位置的颜色词也剥（如 "Watch6 Cyan 44mm"），但 "Gold Edition" 是版本名保留
        words = [w for i, w in enumerate(words)
                 if not (w.lower() in colors and (i + 1 >= len(words) or words[i + 1] != 'Edition'))]
        name = ' '.join(words)
        name = re.sub(r'(\d)m$', r'\1mm', name)  # 源表笔误 40m/43m -> 40mm/43mm
        watch_groups.setdefault(name, []).append(byte)
    for model_name, bytes_ in sorted(watch_groups.items()):
        rules = [_mfr_rule(WATCH_PREFIX + f'{b:02X}') for b in sorted(bytes_)]
        slug = re.sub(r'[^a-z0-9]+', '-', model_name.lower()).strip('-')
        fleets.append(_fleet(
            f'fleet-easysetup-watch-{slug}', f'Samsung Galaxy {model_name} (EasySetup)',
            'WEARABLE', rules,
            'Galaxy Watch EasySetup pairing broadcast (companyId 0x0075, model byte '
            'after fixed header 010002000101FF000043). Color variants share the fleet. '
            'Source: Flipper ble_spam easysetup.c watch_models (GPL-3.0).'))
    if watch_fallback:
        rules = [_mfr_rule(WATCH_PREFIX + f'{b:02X}') for b in sorted(watch_fallback)]
        fleets.append(_fleet(
            'fleet-easysetup-galaxy-watch', 'Samsung Galaxy Watch (EasySetup)', 'WEARABLE', rules,
            'Galaxy Watch EasySetup pairing broadcast (companyId 0x0075) with fallback/'
            'unnamed model bytes from the source table. Source: Flipper ble_spam easysetup.c (GPL-3.0).'))
    watch_bytes = [int(h, 16) for h, _ in watch_entries]

    buds_block = block('buds_models[]')
    pairs: dict[str, list[str]] = {}
    for hex_value, name in re.findall(r'\{0x([0-9A-Fa-f]{6}),\s*"([^"]+)"\}', buds_block):
        value = int(hex_value, 16)
        key = f'{(value >> 16) & 0xFF:02X}{(value >> 8) & 0xFF:02X}'
        pairs.setdefault(key, []).append(name)
    if pairs:
        rules = [_mfr_rule(BUDS_PREFIX + key) for key in sorted(pairs)]
        all_names = sorted({n for names in pairs.values() for n in names})
        fleets.append(_fleet(
            'fleet-easysetup-galaxy-buds', 'Samsung Galaxy Buds (EasySetup)', 'AUDIO', rules,
            'Galaxy Buds EasySetup pairing broadcast (companyId 0x0075); the 3-byte '
            'model/color code is split by a constant byte, so rules match its first '
            f'two bytes ({len(rules)} variants). Known variants: {", ".join(all_names[:8])}. '
            'Source: Flipper ble_spam easysetup.c (GPL-3.0).'))
    return fleets, {'watch_model_bytes': len(watch_bytes), 'buds_prefixes': len(pairs)}
