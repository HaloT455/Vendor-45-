#!/usr/bin/env python3
"""Check the original Test7 package against the imported vendor."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
from inventory_erofs import sha256

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ZIP = '08f28351d83fe6a4ea7f2c1264943d5a96a944296406eada5ff431f727a6ea36'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('zip', type=Path)
    a = p.parse_args()
    assert sha256(a.zip) == EXPECTED_ZIP, 'This is not the previously matched ZIP'
    m = json.loads((ROOT/'metadata/vendor-image-manifest.json').read_text())
    entries = {e['path']:e for e in m['entries']}
    with zipfile.ZipFile(a.zip) as z:
        hashes = {}
        for name in z.namelist():
            h = hashlib.sha256()
            with z.open(name) as stream:
                for data in iter(lambda:stream.read(1024*1024), b''):
                    h.update(data)
            hashes[name] = h.hexdigest()  # zipfile validates CRC while reading
        image = 'vendor-OneUI8-S8Plus-Test7-Camera-Bixby.img'
        assert hashes[image] == m['source_image_sha256'], 'Image differs'
        checked = 0
        for checksum_file in ['SHA256SUMS.txt', 'IMAGE-SHA256SUM.txt']:
            for line in z.read(checksum_file).decode().splitlines():
                match = re.match(r'^([0-9a-fA-F]{64})\s+\*?(.+)$', line)
                if not match:
                    continue
                digest, name = match.groups()
                name = name.removeprefix('./')
                assert hashes[name] == digest.lower(), name
                checked += 1
        payload = [n for n in hashes if n.startswith('technical/payload/') and not n.endswith('/')]
        assert len(payload) == 6
        for name in payload:
            rel = name.removeprefix('technical/payload/')
            assert hashes[name] == entries[rel]['sha256'], name
    print(json.dumps({'verified':True,'crc_entries':len(hashes),
                      'checksum_lines':checked,'payload_matches':len(payload),
                      'image_sha256':m['source_image_sha256']},indent=2))


if __name__ == '__main__':
    main()
