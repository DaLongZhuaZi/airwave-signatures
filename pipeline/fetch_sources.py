#!/usr/bin/env python3
"""抓取全部上游来源到 pipeline/.cache（可离线复现：已有非空文件不重复下载）。

来源清单与许可证见仓库根目录 sources.yaml / SOURCES.md。
注意：IEEE 的 standards-oui 对默认 UA 返回 HTTP 418，必须带浏览器 UA。
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "*/*",
}

# name -> url（name 同时是缓存文件名）
FILES = {
    # 上游 Fieldwatch（Android）签名目录
    "upstream-catalog.json":
        "https://raw.githubusercontent.com/OffGridPete/Fieldwatch/main/dist/fieldwatch-signatures-v2.json",
    # Theengs Decoder 设备定义（逐个 .h 在 fetch_theengs() 里按 listing 抓）
    "theengs-listing.json":
        "https://api.github.com/repos/theengs/decoder/contents/src/devices",
    # Home Assistant 生态的小米 MiBeacon 产品表（Bluetooth-Devices/xiaomi-ble）
    "xiaomi-ble-devices.py":
        "https://raw.githubusercontent.com/Bluetooth-Devices/xiaomi-ble/main/src/xiaomi_ble/devices.py",
    # IEEE OUI 注册表三件套（MA-L / MA-M / MA-S）
    "oui.csv": "https://standards-oui.ieee.org/oui/oui.csv",
    "mam.csv": "https://standards-oui.ieee.org/oui28/mam.csv",
    "oui36.csv": "https://standards-oui.ieee.org/oui36/oui36.csv",
    # 蓝牙 SIG Assigned Numbers
    "service_uuids.yaml":
        "https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/uuids/service_uuids.yaml",
    "member_uuids.yaml":
        "https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/uuids/member_uuids.yaml",
    "company_identifiers.yaml":
        "https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/company_identifiers/company_identifiers.yaml",
    "appearance_values.yaml":
        "https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/core/appearance_values.yaml",
    # Nordic 镜像的蓝牙编号库（BSD-3，含厂商服务段）
    "nordic-service_uuids.json":
        "https://raw.githubusercontent.com/NordicSemiconductor/bluetooth-numbers-database/master/v1/service_uuids.json",
    # Flipper ble_spam（Momentum-Apps，GPL-3.0）：Fast Pair 型号表 + Samsung EasySetup 表
    "fastpair.c":
        "https://raw.githubusercontent.com/Next-Flip/Momentum-Apps/dev/ble_spam/protocols/fastpair.c",
    "easysetup.c":
        "https://raw.githubusercontent.com/Next-Flip/Momentum-Apps/dev/ble_spam/protocols/easysetup.c",
    # Bruce 固件（GPL-3.0）：Apple Proximity Pairing 型号表
    "bruce-ble-spam.cpp":
        "https://raw.githubusercontent.com/BruceDevices/firmware/main/src/modules/ble/ble_spam.cpp",
    # BlueMaestro 设备类型表（Bluetooth-Devices，MIT）
    "bluemaestro-parser.py":
        "https://raw.githubusercontent.com/Bluetooth-Devices/bluemaestro-ble/main/src/bluemaestro_ble/parser.py",
    # Wireshark manuf（仅作校验交叉参考，不直接进产物；抓不到不阻断构建）
    "manuf": "https://gitlab.com/wireshark/wireshark/-/raw/master/manuf",
    # 上一版 radiodb.bin（airwavefootprints 内置版）——仅用于原样保留来源未明的 cid 段
    "radiodb-previous.bin":
        "https://raw.githubusercontent.com/DaLongZhuaZi/airwavefootprints/main/entry/src/main/resources/rawfile/lookups/radiodb.bin",
}

THEENGS_RAW = "https://raw.githubusercontent.com/theengs/decoder/development/src/devices/"


def fetch(url: str, path: str, retries: int = 3) -> str:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 默认 3 次重试：个别源站会临时 refuse 云厂商 IP（如 IEEE 对 GitHub runner），
    # 退避后通常可达；仍失败才向上抛错让本次构建显式失败（不静默用旧数据）。
    import time
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            with open(path, "wb") as fh:
                fh.write(data)
            sys.stderr.write(f"  fetched {os.path.basename(path)} ({len(data)} bytes)\n")
            return path
        except Exception as exc:
            last_exc = exc
            sys.stderr.write(f"  WARN: fetch {os.path.basename(path)} attempt {attempt + 1}/3 failed: {exc}\n")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise last_exc if last_exc else RuntimeError("fetch failed: " + url)


def fetch_theengs(cache: str) -> int:
    import json
    listing = fetch(FILES["theengs-listing.json"], os.path.join(cache, "theengs-listing.json"))
    entries = json.load(open(listing, encoding="utf-8"))
    count = 0
    failed = 0
    for entry in entries:
        name = entry.get("name") or ""
        if not name.endswith(".h"):
            continue
        # 优先用 listing 自带的 download_url（与 listing 同分支），避免分支漂移 404
        url = entry.get("download_url") or (THEENGS_RAW + name)
        try:
            fetch(url, os.path.join(cache, "theengs-devices", name))
            count += 1
        except Exception as exc:  # 单个文件失败不阻断整批
            failed += 1
            sys.stderr.write(f"  WARN: theengs {name} fetch failed ({exc})\n")
    if failed:
        sys.stderr.write(f"  WARN: theengs {failed} files failed\n")
    return count


def main() -> None:
    os.makedirs(CACHE, exist_ok=True)
    for name, url in FILES.items():
        if name == "theengs-listing.json":
            continue
        if name == "manuf":
            try:
                fetch(url, os.path.join(CACHE, name), retries=1)
            except Exception as exc:  # 交叉参考源，失败只警告
                sys.stderr.write(f"  WARN: manuf fetch failed ({exc}), skipped\n")
            continue
        fetch(url, os.path.join(CACHE, name))
    n = fetch_theengs(CACHE)
    sys.stderr.write(f"  theengs device files: {n}\n")
    sys.stderr.write("fetch complete\n")


if __name__ == "__main__":
    main()
