#!/usr/bin/env python3
"""判断 dist 内容是否真的变了（忽略构建时间戳等易变字段）。

用法: python3 pipeline/dist_changed.py   # 退出码 0=有实质变化, 1=无变化
比较对象: 工作区 dist/ vs git HEAD 里的 dist/。
- catalog: 去掉 exportedAt 后按规范化 JSON 比较（provenance 统计在内，算变化）。
- radiodb.bin: 解析 SPLK 段内容比较（跳过头部构建日期）。
"""
import json
import subprocess
import sys

def head_bytes(path: str) -> bytes | None:
    proc = subprocess.run(["git", "show", f"HEAD:{path}"],
                          capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def catalog_changed() -> bool:
    old_raw = head_bytes("dist/fieldwatch-signatures-v2.json")
    new = json.load(open("dist/fieldwatch-signatures-v2.json", encoding="utf-8"))
    new.pop("exportedAt", None)
    if old_raw is None:
        return True
    old = json.loads(old_raw.decode("utf-8"))
    old.pop("exportedAt", None)
    return json.dumps(old, sort_keys=True, ensure_ascii=False) != \
        json.dumps(new, sort_keys=True, ensure_ascii=False)


def radiodb_changed() -> bool:
    old_raw = head_bytes("dist/radiodb.bin")
    new_raw = open("dist/radiodb.bin", "rb").read()
    if old_raw is None:
        return True
    if old_raw[:4] != b"SPLK" or new_raw[:4] != b"SPLK":
        return old_raw != new_raw
    # SPLK 头 16 字节：magic(4) + version u16 + reserved u16 + builtYmd i32 + nsec i32。
    # 只跳过 builtYmd（偏移 8..12），其余字节全比较——段数据与名称池由构建器
    # 确定性生成（已排序），内容不变则字节不变。
    return old_raw[:8] != new_raw[:8] or old_raw[12:] != new_raw[12:]


def main() -> int:
    changed = catalog_changed() or radiodb_changed()
    print("dist changed" if changed else "dist unchanged (timestamps aside)")
    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())
