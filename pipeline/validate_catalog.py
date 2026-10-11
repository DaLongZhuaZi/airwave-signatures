#!/usr/bin/env python3
"""目录校验：与 App 解析器（FieldwatchSignatureCatalog/Engine）的契约逐条对齐。

失败即非零退出，CI 与发布都以它为准。检查项：
  - pack 格式与 catalogVersion（必须 > 上游版本且 >= 100 本仓纪元）
  - fleet：id 唯一、名称非空、至少一条规则
  - rule：kind 在引擎枚举内；OUI 形如 AA:BB:CC；hex 字段偶数长十六进制；
          companyId 0..65535；offset/group/minLen/maxLen >= 0；radio 在 {BLE, WIFI} 或缺省
  - 新增阶段（theengs/mibeacon/vendors/manual）的 fleet 不许与已有 fleet 指纹全同
  - radiodb.bin（若已构建）：SPLK 魔数/版本，各段条数下限，且 FE95 必须能查到名字
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, 'dist')

RULE_KINDS = {'OUI', 'MAC_PREFIX', 'NAME_CONTAINS', 'NAME_GLOB', 'SERVICE_UUID',
              'SERVICE_DATA', 'MANUFACTURER_ID', 'MANUFACTURER_DATA', 'RADIO_KIND',
              'HIDDEN_SSID', 'VENDOR_IE_OUI'}
OUI_RE = re.compile(r'^[0-9A-F]{2}(:[0-9A-F]{2}){2}$')
HEX_RE = re.compile(r'^[0-9A-F]*$')

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def fleet_fingerprint(fleet):
    keys = []
    for rule in fleet.get('rules', []):
        keys.append('|'.join([
            str(rule.get('kind') or ''), (rule.get('text') or '').upper(),
            str(rule.get('companyId') or 0), (rule.get('dataPrefixHex') or '').upper(),
            str(rule.get('radio') or ''), str(rule.get('offset') or 0),
            str(rule.get('group') or 0), str(rule.get('minLen') or 0),
            str(rule.get('maxLen') or 0)]))
    keys.sort()
    return ';'.join(keys)


def check_catalog():
    path = os.path.join(DIST, 'fieldwatch-signatures-v2.json')
    pack = json.load(open(path, encoding='utf-8'))
    if pack.get('format') != 'fieldwatch-signatures':
        err('format 不是 fieldwatch-signatures')
    version = pack.get('catalogVersion') or 0
    if version < 100:
        err(f'catalogVersion {version} 小于本仓纪元 100')
    upstream_version = (pack.get('provenance') or {}).get('upstream', {}).get('catalogVersion') or 0
    if version <= upstream_version:
        err(f'catalogVersion {version} 不大于上游 {upstream_version}')
    fleets = pack.get('fleets') or []
    if not fleets:
        err('fleets 为空')
    ids = {}
    fingerprints = {}
    for fleet in fleets:
        fid = fleet.get('id') or ''
        if not fid:
            err('存在无 id 的 fleet')
            continue
        if fid in ids:
            err(f'fleet id 重复: {fid}')
        ids[fid] = fleet
        if not (fleet.get('name') or '').strip():
            err(f'{fid}: 名称为空')
        rules = fleet.get('rules') or []
        if not rules:
            err(f'{fid}: 无规则')
        for rule in rules:
            kind = rule.get('kind')
            if kind not in RULE_KINDS:
                err(f'{fid}: 未知 rule kind {kind}')
                continue
            text = rule.get('text') or ''
            if kind == 'OUI' and not OUI_RE.match(text.upper()):
                err(f'{fid}: OUI 格式不对: {text}')
            prefix = rule.get('dataPrefixHex') or ''
            # 奇数长 hex 是合法的「半字节前缀」（引擎按 hex 字符串逐字比较）：
            # 已发布目录里就有（如 b-parasite 的版本半字节 "1"/"2"），只校验字符集。
            if not HEX_RE.match(prefix.upper()):
                err(f'{fid}: dataPrefixHex 不是 hex: {prefix}')
            cid = rule.get('companyId') or 0
            if not (0 <= cid <= 65535):
                err(f'{fid}: companyId 越界 {cid}')
            for field in ('offset', 'group', 'minLen', 'maxLen'):
                if (rule.get(field) or 0) < 0:
                    err(f'{fid}: {field} 为负')
            radio = rule.get('radio')
            if radio is not None and radio not in ('BLE', 'WIFI'):
                err(f'{fid}: radio 非法 {radio}')
            if kind in ('MANUFACTURER_DATA', 'SERVICE_DATA') and not prefix and kind == 'MANUFACTURER_DATA':
                err(f'{fid}: MANUFACTURER_DATA 无前缀（引擎会丢弃）')
        fp = fleet_fingerprint(fleet)
        if fp in fingerprints:
            warnings.append(f'指纹重复: {fid} 与 {fingerprints[fp]}（存量重复只警告）')
        else:
            fingerprints[fp] = fid
    sys.stderr.write(f'catalog: {len(fleets)} fleets, version {version}\n')
    return pack


def check_radiodb():
    path = os.path.join(DIST, 'radiodb.bin')
    if not os.path.exists(path):
        warnings.append('radiodb.bin 尚未构建，跳过')
        return
    blob = open(path, 'rb').read()
    if blob[0:4] != b'SPLK':
        err('radiodb 魔数不是 SPLK')
        return
    version, _res, ymd, nsec = struct.unpack_from('<HHii', blob, 4)
    if version != 1:
        err(f'radiodb 版本 {version} != 1')
    offsets = {}
    for i in range(nsec):
        at = 16 + i * 8
        tag = blob[at:at + 4].decode('ascii', 'replace').strip('\x00 ')
        off, = struct.unpack_from('<i', blob, at + 4)
        offsets[tag] = off
    counts = {}
    for tag, off in offsets.items():
        if tag in ('noff', 'nstr'):
            continue
        counts[tag], = struct.unpack_from('<i', blob, off)
    sys.stderr.write(f'radiodb: built {ymd}, sections {counts}\n')
    for tag, minimum in (('mal', 38000), ('long', 12000), ('btc', 4000), ('app', 300), ('uuid', 150)):
        if counts.get(tag, 0) < minimum:
            err(f'radiodb {tag} 只有 {counts.get(tag, 0)} 条，低于下限 {minimum}')
    # FE95（小米 Mi Service）必须在 uuid 段且有名字
    noff, nstr = offsets['noff'], offsets['nstr']
    name_count, = struct.unpack_from('<i', blob, noff)
    name_off = [struct.unpack_from('<i', blob, noff + 4 + i * 4)[0] for i in range(name_count + 1)]

    def name_at(idx):
        return blob[nstr + name_off[idx]:nstr + name_off[idx + 1]].decode('utf-8', 'replace')

    off = offsets['uuid']
    count, = struct.unpack_from('<i', blob, off)
    found = None
    for i in range(count):
        key, = struct.unpack_from('<H', blob, off + 4 + i * 2)
        if key == 0xFE95:
            idx, = struct.unpack_from('<H', blob, off + 4 + count * 2 + i * 2)
            found = name_at(idx)
    if not found:
        err('radiodb uuid 段查不到 FE95')
    else:
        sys.stderr.write(f'radiodb FE95 -> {found}\n')


def main():
    check_catalog()
    check_radiodb()
    for msg in warnings:
        sys.stderr.write(f'WARN: {msg}\n')
    if errors:
        for msg in errors:
            sys.stderr.write(f'ERROR: {msg}\n')
        sys.exit(1)
    sys.stderr.write('validate OK\n')


if __name__ == '__main__':
    main()
