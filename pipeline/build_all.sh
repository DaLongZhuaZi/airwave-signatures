#!/bin/sh
# 一键全量构建：抓取 -> 签名目录 -> radiodb -> 校验 -> 补 manifest 的 radiodb 信息
set -e
cd "$(dirname "$0")/.."

python3 pipeline/fetch_sources.py
python3 pipeline/build_catalog.py
python3 pipeline/build_radiodb.py \
    --out dist/radiodb.bin \
    --cache-dir pipeline/.cache \
    --existing pipeline/.cache/radiodb-previous.bin

python3 - << 'EOF'
import hashlib, json, os, struct
path = 'dist/radiodb.bin'
blob = open(path, 'rb').read()
version, _res, ymd, nsec = struct.unpack_from('<HHii', blob, 4)
counts = {}
for i in range(nsec):
    at = 16 + i * 8
    tag = blob[at:at + 4].decode('ascii', 'replace').strip('\x00 ')
    off, = struct.unpack_from('<i', blob, at + 4)
    if tag not in ('noff', 'nstr'):
        counts[tag], = struct.unpack_from('<i', blob, off)
manifest = json.load(open('dist/manifest.json', encoding='utf-8'))
manifest['radiodb'] = {
    'file': 'radiodb.bin',
    'builtYmd': ymd,
    'sections': counts,
    'sha256': hashlib.sha256(blob).hexdigest(),
}
json.dump(manifest, open('dist/manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('radiodb manifest updated:', counts)
EOF

python3 pipeline/validate_catalog.py
echo "BUILD OK"
