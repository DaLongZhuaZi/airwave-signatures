#!/usr/bin/env python3
"""Theengs Decoder 设备定义 -> Fieldwatch 签名规则（模块版）。

基底来自 airwavefootprints 仓库 scripts/fieldwatch-data/build-catalog.py，
在本仓库做了四处表达力修复（每处都有实测依据，见 SOURCES.md）：

  1. 一个 .h 文件里可能有多个设备 JSON（tracker_json.h 里有 nut/nutale/tile…），
     原实现每文件只取第一个，其余静默丢失。改为 finditer 全取。
  2. `name` 条件的取值是字面名称（如 "nut"），不是十六进制 —— 原实现用
     十六进制正则校验后整台丢弃。改为 name 段跳过 hex 校验，生成 NAME_CONTAINS。
  3. `uuid contain fee0` 这类条件原被 'contain' 黑名单整台丢弃；对 uuid 段
     而言 contain 就是 SERVICE_UUID 匹配，放行。
  4. 纯长度段（如 ["servicedata","=",24]，没有数据取值）原被误当成数据前缀
     "24"；改为长度约束标记，挂到同组同类型的数据规则上，无同组规则时丢弃该段
     （弱化而不误报）。另外主条件不可表达时回退到设备的 conditionnomac。

仍然不可表达、整台跳过的：mac@index（设备个体 MAC，本就不该做 fleet）、
no-mfgdata / not_（否定/缺失判定，引擎无此语义）。

关键约定（与原脚本一致，踩过坑）：
  - 制造商数据公司 ID 是前 2 字节小端：4c0010 -> 公司 ID 0x004C、前缀 10。
  - App 解析时 manufacturerDataHex / serviceData 已剥掉公司 ID / UUID，
    外部库下标 N 映射为 N - 2（HEADER_BYTES）。
"""
import json
import os
import re

HEADER_BYTES = 2
UNSUPPORTED_TOKENS = ('mac@index', 'no-mfgdata', 'not_')

# 由 build_catalog 注入：SIG 采纳服务 UUID 集合（十六进制大写字符串）。
# 单条 SERVICE_UUID 规则只有在 UUID 不是采纳服务时才有辨识力。
ADOPTED_UUIDS = set()


def load_theengs_devices(cache_dir):
    """从缓存目录读全部 Theengs 设备 JSON（一个文件可多台）。"""
    devices = []
    dev_dir = os.path.join(cache_dir, 'theengs-devices')
    if not os.path.isdir(dev_dir):
        return devices
    pattern = re.compile(r'const char\*\s+_\w+\s*=\s*"(.*?)"\s*;', re.S)
    for name in sorted(os.listdir(dev_dir)):
        if not name.endswith('.h'):
            continue
        text = open(os.path.join(dev_dir, name), encoding='utf-8', errors='replace').read()
        for m in pattern.finditer(text):
            try:
                parsed = json.loads(m.group(1).replace('\\"', '"'))
            except Exception:
                continue
            # 文件里还有公共属性等非设备 JSON（无 model_id / condition），滤掉。
            if isinstance(parsed, dict) and parsed.get('model_id') \
                    and (parsed.get('condition') or parsed.get('conditionnomac')):
                devices.append(parsed)
    return devices


def company_id_of(hex_upper):
    """制造商数据的前 2 字节是小端公司 ID：4C0010 -> 0x004C。"""
    if len(hex_upper) < 4:
        return 0
    return int(hex_upper[2:4] + hex_upper[0:2], 16)


def split_condition(cond):
    """把中缀条件切成 [(operator, segment)]；operator 是段**之前**的连接符，首段为 None。"""
    out = []
    current = []
    operator = None
    for token in cond:
        if token in ('&', '|'):
            out.append((operator, current))
            operator = token
            current = []
        else:
            current.append(token)
    out.append((operator, current))
    return out


def segment_to_rule(segment):
    """一个条件段 -> (kind, companyId, prefix, uuidText, offset, minLen, maxLen)。

    纯长度段返回 ('__LEN__', head, '', '', 0, minLen, maxLen)，由 expressible 处理。
    不可表达返回 None。
    """
    if not segment:
        return None
    head = str(segment[0])
    for token in segment:
        text = str(token)
        for bad in UNSUPPORTED_TOKENS:
            if bad in text:
                return None
        if 'contain' in text and head != 'uuid':
            return None
    # 纯长度段：[head, op, number]，没有任何数据取值。
    if len(segment) == 3 and str(segment[1]) in ('=', '>=', '<='):
        try:
            length_value = int(segment[2])
        except (TypeError, ValueError):
            return None
        op = str(segment[1])
        min_len = length_value if op in ('=', '>=') else 0
        max_len = length_value if op == '=' else 0
        return ('__LEN__', head, '', '', 0, min_len, max_len)
    index = None
    length_op = None
    length_value = 0
    for position, token in enumerate(segment):
        text = str(token)
        if text == 'index' and position + 1 < len(segment):
            index = int(segment[position + 1])
        elif text in ('=', '>=', '<=') and position + 1 < len(segment):
            length_op = text
            length_value = int(segment[position + 1])
    if head == 'name':
        # 名称取值是字面文本，不是 hex。
        name_value = str(segment[-1])
        if not name_value:
            return None
        return ('NAME_CONTAINS', 0, '', name_value, 0, 0, 0)
    value = str(segment[-1]).upper()
    if not re.fullmatch(r'[0-9A-F]+', value):
        return None
    # 外部库的 servicedata 含 2 字节 UUID、manufacturerdata 含 2 字节公司 ID。
    offset = max(0, (index or HEADER_BYTES) - HEADER_BYTES)
    min_len = length_value if length_op in ('=', '>=') else 0
    max_len = length_value if length_op == '=' else 0
    if head == 'manufacturerdata':
        # index > 0 的单字节片段是负载中段的数据，压根不含公司 ID（原实现在此整台丢弃）。
        # 只修这一支：index == 0 与长片段保持原语义，保证已发布 fleet 的规则不变。
        # 1/3 个 hex 字符的片段是半字节级模式，字节级引擎表达不了，仍跳过。
        if index is not None and index > 0 and len(value) == 2:
            return ('MANUFACTURER_DATA', 0, value, '', offset, min_len, max_len)
        cid = company_id_of(value)
        rest = value[4:]
        if not rest:
            # 没有前缀：只能退化成「只看公司 ID」，且公司 ID 为 0 时永远匹配不上。
            return None if cid == 0 else ('MANUFACTURER_ID', cid, '', '', 0, 0, 0)
        return ('MANUFACTURER_DATA', cid, rest, '', offset, min_len, max_len)
    if head == 'servicedata':
        return ('SERVICE_DATA', 0, value, '', offset, min_len, max_len)
    if head == 'uuid':
        return ('SERVICE_UUID', 0, '', value, 0, 0, 0)
    return None


def expressible(device):
    """把设备条件翻译成规则列表；返回 [(kind, cid, prefix, uuidText, offset, minLen, maxLen, group)] 或 None。

    `|` 分段、`&` 组内相连：**同组 AND、组间 OR**。
    主条件不可表达时回退 conditionnomac。
    """
    for cond_key in ('condition', 'conditionnomac'):
        cond = device.get(cond_key) or []
        if not cond:
            continue
        result = _expressible_condition(cond)
        if result is not None:
            return result
    return None


def _expressible_condition(cond):
    pieces = split_condition(cond)
    # 按 | 归组：连续被 & 连接的段同属一组。
    groups = []
    current = []
    for operator, segment in pieces:
        if operator == '|' and current:
            groups.append(current)
            current = []
        current.append(segment)
    if current:
        groups.append(current)
    translated_groups = []
    for segments in groups:
        parsed_segments = []
        len_markers = []  # (head, minLen, maxLen)
        for segment in segments:
            parsed = segment_to_rule(segment)
            if parsed is None:
                return None
            if parsed[0] == '__LEN__':
                len_markers.append((parsed[1], parsed[5], parsed[6]))
            else:
                parsed_segments.append(parsed)
        # 纯长度约束挂到同组同类型的数据规则上；没有同类规则就丢弃该约束（弱化）。
        for head, mn, mx in len_markers:
            target_kind = 'MANUFACTURER_DATA' if head == 'manufacturerdata' else \
                'SERVICE_DATA' if head == 'servicedata' else None
            applied = False
            if target_kind:
                for i, rule in enumerate(parsed_segments):
                    if rule[0] == target_kind:
                        parsed_segments[i] = rule[:5] + (mn, mx)
                        applied = True
                        break
            _ = applied
        if not parsed_segments:
            return None
        translated_groups.append(parsed_segments)
    translated = [rule for group in translated_groups for rule in group]
    if not translated:
        return None
    # 弱片段守卫：某个 OR 组若只剩一条「无公司 ID、短前缀」的厂商数据规则，
    # 单独命中会大面积误报（典型：Apple Watch 条件里的中段字节片段，
    # 在 Theengs 的从左到右语义下它本与公司 ID 段是 AND 关系，本引擎的分组
    # 语义表达不了这种优先级）。整台跳过，不冒险。
    for group_rules in translated_groups:
        if len(group_rules) == 1:
            kind, cid, prefix = group_rules[0][0], group_rules[0][1], group_rules[0][2]
            if kind == 'MANUFACTURER_DATA' and cid == 0 and len(prefix) < 6:
                return None
    # 丢弃「单条 SERVICE_UUID 且是 SIG 采纳服务」的条件：采纳服务（如 0x180F 电池）
    # 几乎人人广播，不构成身份。厂商自定义 UUID（FEE0/FE95/FCD2…）不在此列，
    # 它们本身就是厂商协议标识。
    if len(translated) == 1 and translated[0][0] == 'SERVICE_UUID':
        uuid_text = (translated[0][3] or '').upper()
        is_adopted = uuid_text in ADOPTED_UUIDS or (
            len(uuid_text) == 4 and 0x1800 <= int(uuid_text, 16) <= 0x18FF)
        if is_adopted:
            return None
    multi_group = len(translated_groups) > 1 or (len(translated_groups) == 1 and len(translated_groups[0]) > 1)
    out = []
    for group_index, segments in enumerate(translated_groups):
        for parsed in segments:
            group = (group_index + 1) if multi_group else 0
            out.append(parsed + (group,))
    return out


def rule_identity(rule):
    """规则级身份键。必须包含 offset / group / 长度 —— 否则「同前缀不同偏移」会被误判为重复。"""
    return (str(rule.get('kind') or ''),
            (rule.get('text') or '').upper(),
            int(rule.get('companyId') or 0),
            (rule.get('dataPrefixHex') or '').upper(),
            int(rule.get('offset') or 0),
            int(rule.get('group') or 0),
            int(rule.get('minLen') or 0),
            int(rule.get('maxLen') or 0))


def core_identity(rule):
    """规则的核心模式（不含 offset / 长度）—— 用于判断「是否已被覆盖」。"""
    return (str(rule.get('kind') or ''),
            (rule.get('text') or '').upper(),
            int(rule.get('companyId') or 0),
            (rule.get('dataPrefixHex') or '').upper())


def covered_by(candidate, existing_list):
    """candidate 是否被某条既有规则覆盖（既有规则至少同样宽泛）。判据见原脚本注释。"""
    core = core_identity(candidate)
    for rule in existing_list:
        if core_identity(rule) != core:
            continue
        if int(rule.get('offset') or 0) != int(candidate.get('offset') or 0):
            continue
        old_min = int(rule.get('minLen') or 0)
        old_max = int(rule.get('maxLen') or 0)
        new_min = int(candidate.get('minLen') or 0)
        new_max = int(candidate.get('maxLen') or 0)
        if old_min != 0 and old_min > new_min:
            continue
        if old_max != 0 and (new_max == 0 or old_max < new_max):
            continue
        return True
    return False


def existing_keys(catalog):
    keys = set()
    rules = []
    ids = set()
    for fleet in catalog.get('fleets', []):
        ids.add(fleet.get('id'))
        for rule in fleet.get('rules', []):
            keys.add(rule_identity(rule))
            rules.append(rule)
    return keys, rules, ids


def slug(text):
    out = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return out or 'unknown'


def build_fleet(device, rules):
    """把一台设备的多条已翻译规则组装成 fleet。"""
    model_id = device.get('model_id') or 'UNKNOWN'
    brand = (device.get('brand') or '').strip()
    model = (device.get('model') or '').strip() or model_id
    if brand and brand.upper() != 'GENERIC' and brand.lower() not in model.lower():
        name = brand + ' ' + model
    else:
        name = model
    out_rules = []
    for kind, cid, prefix, uuid_text, offset, min_len, max_len, group in rules:
        rule = {
            'kind': kind,
            'text': uuid_text,
            'companyId': cid,
            'dataPrefixHex': prefix,
            'radio': 'BLE',
            'enabled': True,
        }
        if offset > 0:
            rule['offset'] = offset
        if group > 0:
            rule['group'] = group
        if min_len > 0:
            rule['minLen'] = min_len
        if max_len > 0:
            rule['maxLen'] = max_len
        out_rules.append(rule)
    return {
        'id': 'fleet-theengs-' + slug(model_id),
        'name': name,
        'enabled': True,
        'matchAny': True,
        'colorIndex': 4,
        'rules': out_rules,
        'minPeers': 0,
        'peerWindowSec': 60,
        'clusterByOui': False,
        'sequentialMac': False,
        'notes': 'Theengs Decoder device definition (build-time generated).',
        'attentionNote': '',
        'builtIn': True,
    }


def convert(cache_dir, catalog):
    """对已装载的上游目录做 Theengs 富化。返回 (added_fleets, stats dict)。"""
    existing_rule_keys, existing_rules, ids = existing_keys(catalog)
    devices = load_theengs_devices(cache_dir)
    added = []
    skipped_existing = 0
    skipped_unexpressible = 0
    for device in devices:
        parsed = expressible(device)
        if parsed is None:
            skipped_unexpressible += 1
            continue
        fleet = build_fleet(device, parsed)
        if fleet['id'] in ids:
            skipped_existing += 1
            continue
        if all(rule_identity(rule) in existing_rule_keys or covered_by(rule, existing_rules)
               for rule in fleet['rules']):
            skipped_existing += 1
            continue
        ids.add(fleet['id'])
        added.append(fleet)
    stats = {
        'devices_parsed': len(devices),
        'added': len(added),
        'skipped_existing_or_covered': skipped_existing,
        'skipped_unexpressible': skipped_unexpressible,
    }
    return added, stats
