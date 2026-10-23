#!/usr/bin/env python3
"""Offline SIM reference regression gate for S8+ Android16 vendor trial.

The reference vendor.new.dat.br image was supplied by the owner as SIM-working.
Only small plain-text init/VINTF hashes were extracted and compared byte-for-byte.
Radio binary hashes here are those of the existing GitHub Test7 source, not
independently verified against the uploaded compressed EROFS reference.
CI cannot demonstrate registration, LTE service, calls, or safe booting.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"

# SHA256 confirmed by extracting these files from the owner's OTA EROFS.
REFERENCE_TEXT = {
    "etc/init/init.vendor.rilcommon.rc": "c61001ec4a485b436c99fb2d55786aabd92d6fc9f5e4b1b9beff458eb31be610",
    "etc/init/vendor.sem.rilchip.rc": "f3e6eb2e5330a3ba5e1a650ca6fc39b0b9ba25b9843743b7da8f15632a83380f",
    "etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml": "f7d0dfced1b52feb24202d9d8ce1e179dfd67f4c57d42081f57171da03922f2f",
    "etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml": "ad87982c72367cea3f368a023db52ef9a0b7da512d2b9689db8e3ccd89987afe",
}
# Matching these existing vendor Test7 hashes prevents accidental copying
# of unrelated RIL blobs. It does NOT establish a match to the OTA reference.
PRESERVE_SOURCE_BINARY = {
    "bin/hw/rild", "bin/cbd", "bin/secril_config_svc",
    "lib64/libsec-ril.so", "lib64/libril_sem.so",
    "lib64/libsecril-client.so", "lib/libsecril-client.so",
}

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run() -> dict:
    issues = []
    for rel, expected in REFERENCE_TEXT.items():
        file = VENDOR / rel
        if not file.is_file() or sha(file) != expected:
            issues.append("Reference text checksum mismatch: " + rel)

    original = json.loads((ROOT / "metadata/vendor-image-manifest.json").read_text())
    entries = {i["path"]: i for i in original["entries"]}
    for rel in sorted(PRESERVE_SOURCE_BINARY):
        src = VENDOR / rel
        entry = entries.get(rel, {})
        if not src.is_file() or src.stat().st_size != entry.get("size") or sha(src) != entry.get("sha256"):
            issues.append("Source Test7 RIL binary modified: " + rel)

    radio = ET.parse(VENDOR / "etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml").getroot()
    rtexts = [v.text.strip() for v in radio.iter("fqname") if v.text]
    if not {"@1.6::IRadio/slot1", "@1.6::IRadio/slot2"}.issubset(rtexts):
        issues.append("Missing original two Android radio HAL slots")

    seh = ET.parse(VENDOR / "etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml").getroot()
    sehslots = set()
    for hal in seh.findall("hal"):
        if hal.findtext("name") == "vendor.samsung.hardware.radio":
            for interface in hal.findall("interface"):
                if interface.findtext("name") == "ISehRadio":
                    sehslots.update(x.text for x in interface.findall("instance"))
    if not {"slot1", "slot2"}.issubset(sehslots):
        issues.append("Missing Samsung ISehRadio dual-slot instances")

    initrc = (VENDOR / "etc/init/init.vendor.rilcommon.rc").read_text()
    if initrc.count("exec_start network_config") != 1 or initrc.count(
        "setprop ro.telephony.default_network ${ro.vendor.radio.default_network}"
    ) != 1:
        issues.append("Source-matched network init lost")
    props = (VENDOR / "build.prop").read_text()
    if props.count("ro.telephony.default_network=9,9\n") != 1:
        issues.append("Android16 per-phone network defaults changed")
    if props.count("ro.radio.noril=no\n") < 1:
        issues.append("Original modem enabled property missing")

    result = {
        "status": "PASS_STATIC" if not issues else "FAIL_STATIC",
        "reference": "owner-supplied vendor.new.dat.br and boot.img, 2026-10-23",
        "text_files_byte_matched_to_reference": len(REFERENCE_TEXT),
        "radio_binary_checks": "match existing GitHub Test7 manifest only; OTA binary hashes unverified",
        "sim_registration_verified_by_ci": False,
        "legacy_ro_default_setprop_expected_on_branch": True,
        "ro_default_setprop_can_fail_when_property_immutable": True,
        "boot_compatibility_verified_by_ci": False,
        "safe_to_flash": False,
        "errors": issues,
    }
    print(json.dumps(result, indent=2))
    if issues:
        raise SystemExit(1)
    return result

if __name__ == "__main__":
    run()
