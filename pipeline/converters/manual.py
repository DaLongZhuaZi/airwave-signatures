#!/usr/bin/env python3
"""手工 fleet：fleets/manual/*.json，一文件一 fleet（完整 fleet 对象）。

用于协议级与国内特化特征 —— 公开库里没有成表、只能人工维护的部分。
每个文件必须带 notes 说明指纹出处（抓包/官方文档/注册表），无出处的不要进。
"""
import glob
import json
import os


def convert(manual_dir):
    fleets = []
    for path in sorted(glob.glob(os.path.join(manual_dir, '*.json'))):
        with open(path, encoding='utf-8') as fh:
            fleet = json.load(fh)
        fleet.setdefault('enabled', True)
        fleet.setdefault('builtIn', True)
        fleets.append(fleet)
    return fleets, {'manual_fleets': len(fleets)}
