#!/usr/bin/env python3
"""合并构建签名目录：上游 Fieldwatch -> Theengs -> MiBeacon -> IEEE 厂商 -> 手工 fleet。

产物（dist/）：
  fieldwatch-signatures-v2.json  全量目录（App 在线更新与内置快照的唯一来源）
  cn-pack.json                   仅国内相关新增/增补 fleet 的可导入包（供上游 Fieldwatch 用户）
  manifest.json                  版本、条数、来源统计、SHA-256（radiodb 在 build_all 里补）

catalogVersion 由 pipeline/VERSION 决定（单调递增，发布时 +1），不随上游版本号走，
避免重演「App 内置 89、更新源 88」的倒退。
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, '.cache')
sys.path.insert(0, HERE)

from converters import (  # noqa: E402
    theengs, xiaomi_mibeacon, ieee_vendors, manual,
    fastpair, apple_proximity, samsung_easysetup, bluemaestro, blemonitor,
)


def fleet_fingerprint(fleet):
    """与 App 的 signatureFleetFingerprint 同义：规则身份集合 + 匹配模式。"""
    keys = []
    for rule in fleet.get('rules', []):
        keys.append('|'.join([
            str(rule.get('kind') or ''),
            (rule.get('text') or '').upper(),
            str(rule.get('companyId') or 0),
            (rule.get('dataPrefixHex') or '').upper(),
            str(rule.get('radio') or ''),
            str(rule.get('offset') or 0),
            str(rule.get('group') or 0),
            str(rule.get('minLen') or 0),
            str(rule.get('maxLen') or 0),
        ]))
    keys.sort()
    return '|'.join([
        'ANY' if fleet.get('matchAny', True) else 'ALL',
        str(fleet.get('minPeers') or 0),
        str(fleet.get('peerWindowSec') or 60),
        ';'.join(keys),
    ])


def load_adopted_uuids():
    """从 SIG service_uuids.yaml 提取采纳服务 UUID 集合（给 theengs 的单 UUID 判据）。"""
    import re
    path = os.path.join(CACHE, 'service_uuids.yaml')
    out = set()
    if os.path.exists(path):
        text = open(path, encoding='utf-8').read()
        for m in re.finditer(r'uuid:\s*0x([0-9A-Fa-f]{1,4})', text):
            out.add(m.group(1).upper().zfill(4))
    return out


def main():
    version = int(open(os.path.join(HERE, 'VERSION'), encoding='utf-8').read().strip())
    upstream = json.load(open(os.path.join(CACHE, 'upstream-catalog.json'), encoding='utf-8'))
    catalog = {
        'format': 'fieldwatch-signatures',
        'formatVersion': 1,
        'exportedAt': '',
        'appVersion': 'stock',
        'catalogVersion': upstream.get('catalogVersion', 0),
        'fleets': list(upstream.get('fleets', [])),
    }
    stats = {'upstream': {'catalogVersion': upstream.get('catalogVersion'),
                          'fleets': len(catalog['fleets'])}}
    known_ids = {f.get('id') for f in catalog['fleets']}
    known_fps = {fleet_fingerprint(f) for f in catalog['fleets']}
    cn_fleet_ids = []

    def add_fleets(fleets, stage, cn=False):
        added = 0
        for fleet in fleets:
            if fleet.get('id') in known_ids:
                continue
            fp = fleet_fingerprint(fleet)
            if fp in known_fps:
                continue
            catalog['fleets'].append(fleet)
            known_ids.add(fleet.get('id'))
            known_fps.add(fp)
            added += 1
            if cn:
                cn_fleet_ids.append(fleet.get('id'))
        stats[stage] = {'added': added}
        return added

    # 阶段 1：Theengs 富化
    theengs.ADOPTED_UUIDS = load_adopted_uuids()
    theengs_added, theengs_stats = theengs.convert(CACHE, catalog)
    add_fleets(theengs_added, 'theengs')
    stats['theengs'].update(theengs_stats)

    # 阶段 2：小米 MiBeacon 产品表
    xiaomi_fleets, xiaomi_stats = xiaomi_mibeacon.convert(CACHE)
    add_fleets(xiaomi_fleets, 'xiaomi_mibeacon', cn=True)
    stats['xiaomi_mibeacon'].update(xiaomi_stats)

    # 阶段 3：IEEE 厂商（新建 + 增补已有薄 fleet）
    vendor_config = os.path.join(ROOT, 'fleets', 'vendors.json')
    new_vendor_fleets, augments, vendor_stats = ieee_vendors.convert(CACHE, vendor_config, catalog)
    add_fleets(new_vendor_fleets, 'ieee_vendors_new', cn=True)
    stats['ieee_vendors'] = vendor_stats
    augmented = {}
    by_id = {f.get('id'): f for f in catalog['fleets']}
    for fleet_id, extra_rules in augments.items():
        target = by_id.get(fleet_id)
        if target is None:
            continue
        target['rules'].extend(extra_rules)
        augmented[fleet_id] = len(extra_rules)
        if fleet_id not in cn_fleet_ids:
            cn_fleet_ids.append(fleet_id)
    stats['ieee_vendors_augmented'] = augmented

    # 阶段 4：社区逆向汇编的配对/型号表（Flipper/Bruce/HA 生态，均为事实性编码表）
    for stage_name, module in (('fastpair', fastpair), ('apple_proximity', apple_proximity),
                               ('samsung_easysetup', samsung_easysetup),
                               ('bluemaestro', bluemaestro)):
        stage_fleets, stage_stats = module.convert(CACHE)
        add_fleets(stage_fleets, stage_name)
        stats[stage_name].update(stage_stats)

    # 阶段 4b：ble_monitor 独有品牌识别表（fleets/blemonitor.json，人工提取）
    blemonitor_fleets, blemonitor_stats = blemonitor.convert(ROOT)
    add_fleets(blemonitor_fleets, 'blemonitor')
    stats['blemonitor'].update(blemonitor_stats)

    # 阶段 5：手工 fleet（协议级 + 国内特化）
    manual_fleets, manual_stats = manual.convert(os.path.join(ROOT, 'fleets', 'manual'))
    add_fleets(manual_fleets, 'manual', cn=True)
    stats['manual'].update(manual_stats)

    built_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {
        'format': 'fieldwatch-signatures',
        'formatVersion': 1,
        'exportedAt': built_at,
        'appVersion': 'stock',
        'catalogVersion': version,
        'fleets': catalog['fleets'],
        'provenance': stats,
    }
    dist = os.path.join(ROOT, 'dist')
    os.makedirs(dist, exist_ok=True)
    catalog_path = os.path.join(dist, 'fieldwatch-signatures-v2.json')
    with open(catalog_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=4)
    catalog_sha = hashlib.sha256(open(catalog_path, 'rb').read()).hexdigest()

    cn_pack = {
        'format': 'fieldwatch-signatures',
        'formatVersion': 1,
        'exportedAt': built_at,
        'appVersion': 'stock',
        'catalogVersion': version,
        'fleets': [f for f in catalog['fleets'] if f.get('id') in set(cn_fleet_ids)],
    }
    cn_path = os.path.join(dist, 'cn-pack.json')
    with open(cn_path, 'w', encoding='utf-8') as fh:
        json.dump(cn_pack, fh, ensure_ascii=False, indent=4)

    manifest_path = os.path.join(dist, 'manifest.json')
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            manifest = json.load(open(manifest_path, encoding='utf-8'))
        except Exception:
            manifest = {}
    manifest.update({
        'builtAt': built_at,
        'catalogVersion': version,
        'catalog': {
            'file': 'fieldwatch-signatures-v2.json',
            'fleets': len(catalog['fleets']),
            'rules': sum(len(f.get('rules', [])) for f in catalog['fleets']),
            'sha256': catalog_sha,
        },
        'cnPack': {
            'file': 'cn-pack.json',
            'fleets': len(cn_pack['fleets']),
            'sha256': hashlib.sha256(open(cn_path, 'rb').read()).hexdigest(),
        },
        'sources': stats,
    })
    with open(manifest_path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    sys.stderr.write(f"catalog v{version}: {len(catalog['fleets'])} fleets, "
                     f"{manifest['catalog']['rules']} rules\n")
    for stage, data in stats.items():
        sys.stderr.write(f"  {stage}: {data}\n")


if __name__ == '__main__':
    main()
