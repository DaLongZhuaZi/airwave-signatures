#!/usr/bin/env python3
"""小米 MiBeacon 产品表 -> Fieldwatch 签名规则。

来源：Bluetooth-Devices/xiaomi-ble（Home Assistant 生态的解析库，MIT）
src/xiaomi_ble/devices.py 的 DEVICE_TYPES：{product_id: DeviceEntry(name, model, manufacturer)}。

MiBeacon 广播结构（xiaomi_ble/parser.py 实证）：FE95 服务数据负载 =
帧控制(2B) + product_id(2B, 小端) + 帧计数…。App 的 FieldwatchParsers 已把
服务数据的 UUID 剥掉，所以规则是：
  kind=SERVICE_DATA, text="FE95", offset=2, dataPrefixHex=<PID 小端 hex>

用 ast 解析 devices.py（不执行抓回来的代码），按 (manufacturer, model) 分组：
同一型号的多个 PID 合并为一个 fleet、一条 PID 一条规则、matchAny。
"""
import ast
import os
import re

KIND_BY_KEYWORD = [
    ('lock', 'LOCK'),
    ('toothbrush', 'HEALTH'),
    ('scale', 'HEALTH'),
    ('watch', 'WEARABLE'),
    ('band', 'WEARABLE'),
    ('door', 'HOME'),
    ('window', 'HOME'),
    ('smoke', 'HOME'),
    ('gas', 'HOME'),
    ('switch', 'HOME'),
    ('sensor', 'HOME'),
    ('clock', 'HOME'),
    ('kettle', 'HOME'),
    ('fan', 'HOME'),
    ('light', 'HOME'),
    ('lamp', 'HOME'),
    ('plug', 'HOME'),
    ('faucet', 'HOME'),
    ('plant', 'HOME'),
    ('flower', 'HOME'),
    ('feeder', 'HOME'),
    ('diffuser', 'HOME'),
    ('humidifier', 'HOME'),
    ('curtain', 'HOME'),
    ('remote', 'HOME'),
]


def slug(text):
    out = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return out or 'unknown'


def load_device_types(cache_dir):
    """ast 解析缓存的 xiaomi-ble devices.py，返回 {pid:int -> (name, model, manufacturer)}。"""
    path = os.path.join(cache_dir, 'xiaomi-ble-devices.py')
    tree = ast.parse(open(path, encoding='utf-8').read())
    out = {}
    for node in ast.walk(tree):
        dict_node = None
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'DEVICE_TYPES' for t in node.targets):
            dict_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == 'DEVICE_TYPES':
            dict_node = node.value
        if dict_node is None:
            continue
        for key, value in zip(dict_node.keys, dict_node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, int)):
                continue
            if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == 'DeviceEntry'):
                continue
            fields = {}
            for kw in value.keywords:
                if isinstance(kw.value, ast.Constant):
                    fields[kw.arg] = kw.value.value
            name = fields.get('name') or ''
            model = fields.get('model') or ''
            manufacturer = fields.get('manufacturer') or 'Xiaomi'
            if model:
                out[key.value] = (name, model, manufacturer)
    return out


def kind_of(name, model):
    text = (name + ' ' + model).lower()
    for keyword, kind in KIND_BY_KEYWORD:
        if keyword in text:
            return kind
    return 'HOME'


def convert(cache_dir):
    """返回 (fleets, stats)。fleet id 形如 fleet-mibeacon-<model slug>，同型号多 PID 合并。"""
    device_types = load_device_types(cache_dir)
    groups = {}  # (manufacturer, model) -> {'name':..., 'pids':[...]}
    for pid, (name, model, manufacturer) in sorted(device_types.items()):
        key = (manufacturer, model)
        entry = groups.setdefault(key, {'name': name, 'pids': []})
        entry['pids'].append(pid)
    fleets = []
    used_ids = set()
    for (manufacturer, model), entry in sorted(groups.items()):
        fleet_id = 'fleet-mibeacon-' + slug(model)
        if fleet_id in used_ids:  # 同 slug 不同型号（极少）：用首个 PID 消歧
            fleet_id += '-' + format(entry['pids'][0], '04x')
        used_ids.add(fleet_id)
        pids_text = ', '.join('0x%04X' % pid for pid in entry['pids'])
        rules = []
        for pid in entry['pids']:
            le_hex = bytes([pid & 0xFF, (pid >> 8) & 0xFF]).hex().upper()
            rules.append({
                'kind': 'SERVICE_DATA',
                'text': 'FE95',
                'companyId': 0,
                'dataPrefixHex': le_hex,
                'radio': 'BLE',
                'enabled': True,
                'offset': 2,
            })
        fleets.append({
            'id': fleet_id,
            'name': f'{manufacturer} {model}',
            'enabled': True,
            'matchAny': True,
            'colorIndex': 4,
            'rules': rules,
            'minPeers': 0,
            'peerWindowSec': 60,
            'clusterByOui': False,
            'sequentialMac': False,
            'notes': f'MiBeacon product {pids_text} ({entry["name"]}). '
                     'FE95 service data, product ID at offset 2. '
                     'Source: Bluetooth-Devices/xiaomi-ble DEVICE_TYPES.',
            'attentionNote': '',
            'builtIn': True,
            'kind': kind_of(entry['name'], model),
        })
    stats = {
        'product_ids': len(device_types),
        'fleets': len(fleets),
    }
    return fleets, stats
