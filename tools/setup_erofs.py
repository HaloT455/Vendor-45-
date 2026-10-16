#!/usr/bin/env python3
"""Install the pinned amd64 Debian erofs-utils locally without root."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://deb.debian.org/debian/pool/main/e/erofs-utils/erofs-utils_1.8.6-1_amd64.deb'
SHA256 = '81042b8c0c3eb63699aa7d0763dceedc675a747d9f5cfebf914b4160233f411e'

if __name__ == '__main__':
    destination = ROOT/'.tools'
    destination.mkdir(exist_ok=True)
    package = destination/'erofs-utils_1.8.6-1_amd64.deb'
    if not package.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == SHA256, 'Toolchain checksum mismatch'
        package.write_bytes(data)
    assert hashlib.sha256(package.read_bytes()).hexdigest() == SHA256
    subprocess.run(['dpkg-deb','-x',str(package),str(destination/'erofs')], check=True)
    subprocess.run([str(destination/'erofs/usr/bin/mkfs.erofs'),'-V'], check=True)
