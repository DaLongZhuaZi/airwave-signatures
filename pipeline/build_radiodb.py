#!/usr/bin/env python3
"""从权威来源重新生成 radiodb.bin（Fieldwatch 的 IEEE / 蓝牙名称库）。

为什么要这个脚本：radiodb.bin 是 1.28 MB 的静态 rawfile，内置日期 2026-08-24，
而上游 Fieldwatch 仓库并不托管它（dist/ 下只有目录 JSON，实测 404），
因此它既无法随上游更新，也无法自行刷新 —— 只能长期停在打包那一天。

来源（全部公开权威，实测可达）：
  mal   <- IEEE MA-L                     standards-oui.ieee.org/oui/oui.csv
  long  <- IEEE MA-M (28 位)             standards-oui.ieee.org/oui28/mam.csv
           IEEE MA-S (36 位)             standards-oui.ieee.org/oui36/oui36.csv
  btc   <- 蓝牙 SIG 官方公司 ID           assigned_numbers/company_identifiers/company_identifiers.yaml
  app   <- 蓝牙 SIG 官方 GAP Appearance   assigned_numbers/core/appearance_values.yaml
  uuid  <- 蓝牙 SIG 官方服务 UUID         assigned_numbers/uuids/service_uuids.yaml
           并集 Nordic 镜像的厂商服务段（0xFC00-0xFFFF）
  cid   <- IEEE CID 注册表 cid.csv（v102 起；此前来源未确认的旧段经核对即此表旧快照）

关于 uuid 为什么取并集：官方 service_uuids.yaml 只收采纳服务（0x1800-0x18FF，76 条），
不含厂商/成员服务段；而 0xFCxx-0xFExx 里恰恰是 Fast Pair、Eddystone、暴露通知这些
对被动扫描最有价值的条目。实测旧 bin 与官方 76 条逐条完全一致（含命名风格：官方用 GAP，
Nordic 用 Generic Access），因此以官方为准，只补官方缺失的厂商段。

格式（小端，与 FieldwatchRadioDb.ets 读取端一致）：
  'SPLK' | version:u16 | reserved:u16 | builtYmd:i32 | nsec:i32
  nsec x ( tag:char[4] | offset:i32 )
  各段：n:i32 后跟 n x (key) 再跟 n x (idx:u16)      # 先读完 key 再读 idx
  noff 段：n:i32 后跟 (n+1) x i32 名称偏移
  nstr 段：名称字节池（UTF-8，去重）
  long 段的键是 8 字节：(位宽 << 56) | 前缀值，位宽 28=MA-M、36=MA-S
"""
import argparse, csv, datetime, json, os, re, struct, sys, urllib.request

IEEE = {
    'oui.csv': 'https://standards-oui.ieee.org/oui/oui.csv',
    'mam.csv': 'https://standards-oui.ieee.org/oui28/mam.csv',
    'oui36.csv': 'https://standards-oui.ieee.org/oui36/oui36.csv',
    'cid.csv': 'https://standards-oui.ieee.org/cid/cid.csv',
}
SIG_BASE = 'https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers'
SIG = {
    'service_uuids.yaml': SIG_BASE + '/uuids/service_uuids.yaml',
    'member_uuids.yaml': SIG_BASE + '/uuids/member_uuids.yaml',
    'company_identifiers.yaml': SIG_BASE + '/company_identifiers/company_identifiers.yaml',
    'appearance_values.yaml': SIG_BASE + '/core/appearance_values.yaml',
}
NORDIC_VENDOR = ('https://raw.githubusercontent.com/NordicSemiconductor/'
                 'bluetooth-numbers-database/master/v1/service_uuids.json')

KEY_BYTES = {'mal': 4, 'cid': 4, 'long': 8, 'btc': 2, 'app': 2, 'uuid': 2}

UUID_NAME_OVERRIDES = {
    0xFE95: 'Xiaomi Mi Service (MiBeacon)',
    0xFCD2: 'BTHome',
}
ORDER = ['mal', 'cid', 'long', 'btc', 'app', 'uuid']
NL = chr(10)


def fetch(cache_dir, name, url):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        sys.stderr.write('  下载 %s%s' % (name, NL))
        # IEEE 的 standards-oui 会对 urllib 默认 UA 返回 **HTTP 418**（反爬），
        # 必须带一个浏览器 UA 才能取到。这是实测踩到的坑。
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept': '*/*',
        })
        with urllib.request.urlopen(request, timeout=180) as resp:
            data = resp.read()
        with open(path, 'wb') as fh:
            fh.write(data)
    return path


def strip_quotes(text):
    text = (text or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in (chr(39), chr(34)):
        return text[1:-1]
    return text


def read_ieee(path, expected_len):
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            assignment = (row.get('Assignment') or '').strip().upper()
            org = (row.get('Organization Name') or '').strip()
            if not assignment or not org or len(assignment) > expected_len:
                continue
            try:
                rows.append((int(assignment.rjust(expected_len, '0'), 16), org))
            except ValueError:
                continue
    return rows


def read_sig_service_uuids(path):
    text = open(path, encoding='utf-8').read()
    out = {}
    pattern = r'-\s*uuid:\s*0x([0-9A-Fa-f]{1,4})\s*\n\s*name:\s*(.+)'
    for match in re.finditer(pattern, text):
        out[int(match.group(1), 16)] = strip_quotes(match.group(2))
    return out


def read_sig_company_ids(path):
    text = open(path, encoding='utf-8').read()
    out = {}
    pattern = r'-\s*value:\s*0x([0-9A-Fa-f]{1,4})\s*\n\s*name:\s*(.+)'
    for match in re.finditer(pattern, text):
        out[int(match.group(1), 16)] = strip_quotes(match.group(2))
    return out


def read_sig_appearance(path):
    """官方 appearance_values.yaml -> 展平成 GAP Appearance 数值。

    两级结构：category 可带 subcategory。编码实测自旧 bin：
    无子类 value = category << 6；有子类 value = (category << 6) | sub，
    名称拼成「类别 / 子类」。
    例：0x001 -> 0x0040 Phone；0x002 + 0x01 -> 0x0081 Computer / Desktop Workstation。
    """
    lines = open(path, encoding='utf-8').read().splitlines()
    out = {}
    category = None
    category_name = ''
    in_sub = False
    pending = None
    for line in lines:
        s = line.strip()
        m = re.match(r'-\s*category:\s*0x([0-9A-Fa-f]+)', s)
        if m:
            category = int(m.group(1), 16)
            category_name = ''
            in_sub = False
            pending = None
            continue
        if category is None:
            continue
        if s.startswith('subcategory:'):
            in_sub = True
            continue
        m = re.match(r'-\s*value:\s*0x([0-9A-Fa-f]+)', s)
        if m:
            pending = (category << 6) | int(m.group(1), 16)
            continue
        if s.startswith('name:'):
            name = strip_quotes(s[len('name:'):])
            if in_sub and pending is not None:
                out[pending] = '%s / %s' % (category_name, name)
                pending = None
            elif not in_sub:
                category_name = name
                out[category << 6] = name
    return out


def read_nordic_vendor_uuids(path):
    """Nordic 蓝牙编号库的服务 UUID 全量（BSD-3 镜像）。

    本仓修复点：原版只取 0xFC00-0xFFFF，漏掉 FE/FD 段的大量成员服务
    （FE95 小米 Mi Service、FD3D SwitchBot 等恰在 FE/FD 段）。
    改为全量并入，优先级低于 SIG 官方两表（官方命名为准）。
    """
    items = json.load(open(path, encoding='utf-8'))
    out = {}
    for item in items:
        raw = (item.get('uuid') or '').strip()
        name = (item.get('name') or '').strip()
        if len(raw) != 4 or not name:
            continue
        value = int(raw, 16)
        out[value] = name
    return out


def parse_existing(path):
    """读出既有 bin，用于保留 cid 并做基线对比。"""
    blob = open(path, 'rb').read()
    if blob[0:4] != b'SPLK':
        raise SystemExit('现有 bin magic 不是 SPLK')
    (nsec,) = struct.unpack_from('<i', blob, 12)
    offsets = {}
    for index in range(nsec):
        at = 16 + index * 8
        tag = blob[at:at + 4].decode('ascii', 'replace').strip(chr(0) + ' ')
        (off,) = struct.unpack_from('<i', blob, at + 4)
        offsets[tag] = off
    noff, nstr = offsets['noff'], offsets['nstr']
    (name_count,) = struct.unpack_from('<i', blob, noff)
    name_off = [struct.unpack_from('<i', blob, noff + 4 + i * 4)[0] for i in range(name_count + 1)]

    def name_at(index):
        if index < 0 or index + 1 >= len(name_off):
            return ''
        return blob[nstr + name_off[index]:nstr + name_off[index + 1]].decode('utf-8', 'replace')

    sections = {}
    for tag, off in offsets.items():
        if tag in ('noff', 'nstr'):
            continue
        (count,) = struct.unpack_from('<i', blob, off)
        kb = 8 if tag == 'long' else (4 if tag in ('mal', 'cid') else 2)
        at = off + 4
        keys = []
        for index in range(count):
            if kb == 8:
                lo = struct.unpack_from('<I', blob, at + index * 8)[0]
                hi = struct.unpack_from('<I', blob, at + index * 8 + 4)[0]
                keys.append(((hi >> 24) & 0xFF, lo + (hi & 0xFFFFFF) * 4294967296))
            elif kb == 4:
                keys.append(struct.unpack_from('<I', blob, at + index * 4)[0])
            else:
                keys.append(struct.unpack_from('<H', blob, at + index * 2)[0])
        at += count * kb
        idx = [struct.unpack_from('<H', blob, at + index * 2)[0] for index in range(count)]
        sections[tag] = {keys[i]: name_at(idx[i]) for i in range(count)}
    return sections


def build_sections(args):
    cache = args.cache_dir
    out = {}
    mal = read_ieee(fetch(cache, 'oui.csv', IEEE['oui.csv']), 6)
    out['mal'] = sorted(set(mal))
    sys.stderr.write('  mal  %d 条%s' % (len(out['mal']), NL))
    # IEEE CID 注册表（EUI-48 的 Company ID 段）：v101 之前此段来源未确认、只能从
    # 旧 bin 原样保留；官方 cid.csv 与 oui.csv 同构（221 条，2026-10 实测），
    # 从 v102 起直接用官方表构建，抓不到时才回退旧 bin 保留（见 main）。
    try:
        cid_entries = read_ieee(fetch(cache, 'cid.csv', IEEE['cid.csv']), 6)
        if cid_entries:
            out['cid'] = sorted(set(cid_entries))
            sys.stderr.write('  cid  %d 条（IEEE CID 官方）%s' % (len(out['cid']), NL))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write('  cid  官方表抓取失败（%s），回退旧 bin 保留%s' % (exc, NL))
    mam = read_ieee(fetch(cache, 'mam.csv', IEEE['mam.csv']), 7)
    mas = read_ieee(fetch(cache, 'oui36.csv', IEEE['oui36.csv']), 9)
    out['long'] = sorted(set([((28, v), n) for v, n in mam] + [((36, v), n) for v, n in mas]))
    sys.stderr.write('  long %d 条 (MA-M %d + MA-S %d)%s' % (len(out['long']), len(mam), len(mas), NL))
    companies = read_sig_company_ids(fetch(cache, 'company_identifiers.yaml', SIG['company_identifiers.yaml']))
    out['btc'] = sorted(companies.items())
    sys.stderr.write('  btc  %d 条（SIG 官方）%s' % (len(out['btc']), NL))
    appearance = read_sig_appearance(fetch(cache, 'appearance_values.yaml', SIG['appearance_values.yaml']))
    out['app'] = sorted(appearance.items())
    sys.stderr.write('  app  %d 条（SIG 官方）%s' % (len(out['app']), NL))
    official = read_sig_service_uuids(fetch(cache, 'service_uuids.yaml', SIG['service_uuids.yaml']))
    member = read_sig_service_uuids(fetch(cache, 'member_uuids.yaml', SIG['member_uuids.yaml']))
    vendor = read_nordic_vendor_uuids(fetch(cache, 'nordic-service_uuids.json', NORDIC_VENDOR))
    merged = dict(official)
    added_member = 0
    for key, name in member.items():
        if key not in merged:
            merged[key] = name
            added_member += 1
    added = 0
    for key, name in vendor.items():
        if key not in merged:
            merged[key] = name
            added += 1
    # 极少数协议关键 UUID 的显示名覆盖：SIG 成员表里只有公司名（如 FE95 = Xiaomi Inc.），
    # 但设备详情里显示协议名才有辨识价值。只许改名、不许新增条目。
    for key, display in UUID_NAME_OVERRIDES.items():
        if key in merged:
            merged[key] = display
    out['uuid'] = sorted(merged.items())
    sys.stderr.write('  uuid %d 条（官方采纳 %d + 成员补 %d + Nordic 补 %d）%s' % (len(out['uuid']), len(official), added_member, added, NL))
    return out


def write_bin(path, sections, built_ymd):
    names = {}
    pool = bytearray()

    def name_index(text):
        if text in names:
            return names[text]
        index = len(names)
        names[text] = index
        pool.extend(text.encode('utf-8'))
        return index

    table = bytearray()
    body = bytearray()
    # 表里除 ORDER 的 6 段还有 noff / nstr，共 len(ORDER) + 2 段 ——
    # 少算这两段会让所有段偏移整体前移 16 字节，读取端读到错位数据。
    cursor = 16 + (len(ORDER) + 2) * 8
    for tag in ORDER:
        entries = sections.get(tag) or []
        table.extend(tag.ljust(4, chr(0)).encode('ascii'))
        table.extend(struct.pack('<i', cursor))
        kb = KEY_BYTES[tag]
        chunk = bytearray()
        chunk.extend(struct.pack('<i', len(entries)))
        for key, _name in entries:
            if kb == 8:
                width, value = key
                chunk.extend(struct.pack('<I', value % 4294967296))
                chunk.extend(struct.pack('<I', (width << 24) | (value // 4294967296)))
            elif kb == 4:
                chunk.extend(struct.pack('<I', key))
            else:
                chunk.extend(struct.pack('<H', key))
        for _key, name in entries:
            chunk.extend(struct.pack('<H', name_index(name)))
        body.extend(chunk)
        cursor += len(chunk)
    table.extend(b'noff')
    table.extend(struct.pack('<i', cursor))
    name_count = len(names)
    ordered = [None] * name_count
    for text, index in names.items():
        ordered[index] = text
    offsets = bytearray()
    offsets.extend(struct.pack('<i', name_count))
    running = 0
    for text in ordered:
        offsets.extend(struct.pack('<i', running))
        running += len(text.encode('utf-8'))
    offsets.extend(struct.pack('<i', running))
    body.extend(offsets)
    cursor += len(offsets)
    table.extend(b'nstr')
    table.extend(struct.pack('<i', cursor))
    blob = bytearray()
    blob.extend(b'SPLK')
    blob.extend(struct.pack('<HH', 1, 0))
    blob.extend(struct.pack('<i', built_ymd))
    blob.extend(struct.pack('<i', len(ORDER) + 2))
    blob.extend(table)
    blob.extend(body)
    blob.extend(pool)
    with open(path, 'wb') as fh:
        fh.write(blob)
    return len(blob), name_count


def main():
    parser = argparse.ArgumentParser(description='从权威来源重新生成 radiodb.bin')
    parser.add_argument('--out', default='radiodb.bin')
    parser.add_argument('--cache-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache'))
    parser.add_argument('--existing', default=None, help='现有 bin（保留 cid，并做基线对比）')
    parser.add_argument('--built-ymd', type=int, default=0)
    args = parser.parse_args()
    built = args.built_ymd or int(datetime.date.today().strftime('%Y%m%d'))
    sections = build_sections(args)
    if args.existing:
        old = parse_existing(args.existing)
        if old.get('cid') and 'cid' not in sections:
            sections['cid'] = sorted(old['cid'].items())
            sys.stderr.write('  cid  %d 条（从现有 bin 保留）%s' % (len(sections['cid']), NL))
        sys.stderr.write(NL + '  基线对比（新 / 旧）：' + NL)
        for tag in ORDER:
            new_set = set(k for k, _ in sections.get(tag) or [])
            old_set = set(old.get(tag, {}).keys())
            lost = old_set - new_set
            sys.stderr.write('    %-5s %7d / %7d   丢失 %d%s' % (tag, len(new_set), len(old_set), len(lost), NL))
            if 0 < len(lost) <= 12:
                for key in sorted(lost):
                    sys.stderr.write('        - %s -> %r%s' % (key, old.get(tag, {})[key], NL))
    size, name_count = write_bin(args.out, sections, built)
    sys.stderr.write(NL + '  写出 %s：%d 字节，名称 %d 个%s' % (args.out, size, name_count, NL))


if __name__ == '__main__':
    main()
