#!/usr/bin/env python3
"""ALICE Android16 experimental RAF RRO safety gates; offline only."""
import argparse
import base64
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    apk = args.apk
    assert apk.is_file() and apk.stat().st_size > 2000
    with zipfile.ZipFile(apk) as zf:
        assert zf.testzip() is None, "Corrupt APK"
        names = set(zf.namelist())
        assert "AndroidManifest.xml" in names, "Missing compiled AndroidManifest.xml"
        assert "resources.arsc" in names, "Missing compiled resource mapping"
        assert any(name.startswith("META-INF/") for name in names), "No APK signature metadata"
    props = (ROOT / "vendor/build.prop").read_text()
    assert "ro.vndk.version=33" in props
    assert "ro.vendor.sec.radio.def_network=9" in props
    assert "ro.vendor.build.version.sdk=33" in props
    for forbidden in ("ro.vndk.version=36", "persist.radio.multisim.config=none",
                      "persist.radio.simslotcount=1", "persist.radio.force_get_pref="):
        assert forbidden not in props, f"Unexpected modem/RIL override: {forbidden}"
    assert "slot1" in (ROOT / "vendor/etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml").read_text()
    assert "slot2" in (ROOT / "vendor/etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml").read_text()
    if args.staged:
        manifest = json.loads((ROOT / "metadata/vendor-image-manifest.json").read_text())
        entry = next(x for x in manifest["entries"] if x["path"] == "overlay/ALICE-RadioRAF/ALICE-RadioRAF.apk")
        assert entry["size"] == apk.stat().st_size
        assert entry["sha256"] == hashlib.sha256(apk.read_bytes()).hexdigest()
        selinux = base64.b64decode(entry["xattrs"]["security.selinux"])
        assert selinux == b"u:object_r:vendor_overlay_file:s0"
        assert "vendor/overlay/ALICE-RadioRAF/ALICE-RadioRAF.apk" in (ROOT / "metadata/vendor_fs_config").read_text()
    print("PASS: verified APK structure, 2-slot HIDL, safe legacy property consistency, stage metadata (when selected)")
    print("NOT CONFIRMED: Android16 idmap approval, real RadioCapability RAF, single-slot LTE, Dual LTE")


if __name__ == "__main__":
    main()
