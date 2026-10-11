#!/usr/bin/env python3
"""IEEE 注册表 -> 厂商 OUI fleet（生成新厂商 + 增补已有厂商）。

与上游目录的厂商 fleet 惯例一致：只用 MA-L（24 位）OUI —— MA-M/MA-S 的
长前缀由 radiodb.bin 的厂商名查询覆盖，不进签名 fleet（上游 304 条里
MAC_PREFIX 也只有 1 条）。

配置在 fleets/vendors.json，每项：
  {
    "name": "Honor",                     # fleet 显示名
    "id": "fleet-honor",                  # 新建时的 id（增补模式不用）
    "org_patterns": ["honor device"],     # 对 IEEE Organization Name 做 regex（小写匹配）
    "name_globs": ["Honor*", "HONOR*"],    # 设备名/SSID 匹配（新建时）
    "kind": "PHONE", "colorIndex": 6,
    "augment": "Honor"                    # 非空 = 把 OUI 规则增补进这个已有 fleet 名（不新建）
    "notes": "..."
  }
匹配纪律：org_patterns 必须能在 probe 报告里逐条对上实际组织名，
宁可漏收一家子公司，也不能误伤无关公司（见 fleets/vendors.md 的审计记录）。
"""
import csv
import json
import os
import re


def load_mal(cache_dir):
    """读 IEEE MA-L csv，返回 [(oui 'AA:BB:CC', org_name)]。"""
    path = os.path.join(cache_dir, 'oui.csv')
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            assignment = (row.get('Assignment') or '').strip().upper()
            org = (row.get('Organization Name') or '').strip()
            if len(assignment) != 6 or not org:
                continue
            oui = ':'.join(assignment[i:i + 2] for i in (0, 2, 4))
            rows.append((oui, org))
    return rows


def oui_rules(ouis):
    return [{
        'kind': 'OUI',
        'text': oui,
        'companyId': 0,
        'dataPrefixHex': '',
        'radio': 'WIFI',
        'enabled': True,
    } for oui in sorted(ouis)]


def convert(cache_dir, config_path, catalog):
    """返回 (new_fleets, augments, stats)。

    augments: {existing_fleet_id: [OUI rules to append]}
    """
    mal = load_mal(cache_dir)
    config = json.load(open(config_path, encoding='utf-8'))
    existing_by_name = {}
    existing_rule_keys = set()
    for fleet in catalog.get('fleets', []):
        existing_by_name[(fleet.get('name') or '').lower()] = fleet
        for rule in fleet.get('rules', []):
            existing_rule_keys.add((fleet.get('id'), rule.get('kind'),
                                    (rule.get('text') or '').upper()))
    new_fleets = []
    augments = {}
    stats = {'vendors': {}, 'augmented_fleets': {}, 'skipped_existing_fleet': []}
    for vendor in config:
        patterns = [re.compile(p) for p in vendor['org_patterns']]
        excludes = [re.compile(p) for p in vendor.get('org_exclude_patterns', [])]
        ouis = set()
        orgs = set()
        for oui, org in mal:
            lowered = org.lower()
            if any(p.search(lowered) for p in excludes):
                continue
            if any(p.search(lowered) for p in patterns):
                ouis.add(oui)
                orgs.add(org)
        stats['vendors'][vendor['name']] = {
            'oui_count': len(ouis),
            'org_names': sorted(orgs),
        }
        if not ouis:
            stats['vendors'][vendor['name']]['skipped_no_mal'] = True
            continue
        rules = oui_rules(ouis)
        augment_name = vendor.get('augment')
        if augment_name:
            target = existing_by_name.get(augment_name.lower())
            if target is None:
                stats['skipped_existing_fleet'].append(augment_name)
                continue
            fresh = [r for r in rules
                     if (target['id'], 'OUI', r['text']) not in existing_rule_keys]
            if fresh:
                augments[target['id']] = fresh
                stats['augmented_fleets'][target['id']] = len(fresh)
            continue
        if vendor['name'].lower() in existing_by_name:
            stats['skipped_existing_fleet'].append(vendor['name'])
            continue
        fleet_rules = []
        for glob in vendor.get('name_globs', []):
            fleet_rules.append({
                'kind': 'NAME_GLOB',
                'text': glob,
                'companyId': 0,
                'dataPrefixHex': '',
                'radio': 'WIFI',
                'enabled': True,
            })
        fleet_rules.extend(rules)
        new_fleets.append({
            'id': vendor['id'],
            'name': vendor['name'],
            'enabled': True,
            'matchAny': True,
            'colorIndex': vendor.get('colorIndex', 6),
            'rules': fleet_rules,
            'minPeers': 0,
            'peerWindowSec': 60,
            'clusterByOui': False,
            'sequentialMac': False,
            'notes': vendor.get('notes', 'IEEE MA-L vendor block. Identifies the vendor, not a specific product.'),
            'attentionNote': '',
            'builtIn': True,
            'kind': vendor.get('kind', 'ISP'),
        })
    return new_fleets, augments, stats
