#!/usr/bin/env python3
"""Offline Test7 Camera/RIL inventory. Never claims physical runtime support."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
CAMERA_BINARIES = [
    "lib/hw/camera.universal8895.so",
    "lib64/hw/camera.universal8895.so",
    "lib/libexynoscamera3.so",
    "lib64/libexynoscamera3.so",
    "bin/hw/vendor.samsung.hardware.camera.provider@4.0-service",
]
RIL_BINARIES = [
    "bin/hw/rild",
    "lib64/libril_sem.so",
    "lib64/libsec-ril.so",
]
RADIO_HIDL = "etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml"
SAMSUNG_RADIO_HIDL = "etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml"
CAMERA_RC = "etc/init/alice-camera-test7.rc"


def parse_manifest(path):
    root = ET.parse(path).getroot()
    fqnames = [
        (el.text or "").strip()
        for el in root.iter("fqname")
        if (el.text or "").strip()
    ]
    named_interfaces = [
        (hal.findtext("name"), interface.findtext("name"),
         [instance.text for instance in interface.findall("instance")])
        for hal in root.iter("hal")
        for interface in hal.findall("interface")
    ]
    return {"fqnames": fqnames, "interfaces": named_interfaces}


def dynamic_needed(path):
    r = subprocess.run(
        ["readelf", "-d", str(path)], capture_output=True, text=True, check=True
    )
    return sorted(set(re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", r.stdout)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="out/audit.json")
    opts = ap.parse_args()

    errors, warnings, binaries = [], [], {}
    required = CAMERA_BINARIES + RIL_BINARIES + [
        RADIO_HIDL, SAMSUNG_RADIO_HIDL, CAMERA_RC, "build.prop"
    ]
    for rel in required:
        if not (VENDOR / rel).is_file():
            errors.append("Missing expected Test7 source file: " + rel)

    for rel in CAMERA_BINARIES + RIL_BINARIES:
        p = VENDOR / rel
        if not p.is_file():
            continue
        if p.open("rb").read(4) != b"\x7fELF":
            errors.append("Not an ELF binary: " + rel)
            continue
        try:
            binaries[rel] = {
                "bytes": p.stat().st_size,
                "needed": dynamic_needed(p),
            }
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append("readelf failed for " + rel + ": " + str(exc))

    manifests = {}
    for rel in [RADIO_HIDL, SAMSUNG_RADIO_HIDL]:
        if (VENDOR / rel).is_file():
            try:
                manifests[rel] = parse_manifest(VENDOR / rel)
            except ET.ParseError as exc:
                errors.append("Malformed HIDL manifest " + rel + ": " + str(exc))

    aosp = manifests.get(RADIO_HIDL, {})
    af = aosp.get("fqnames", [])
    for instance in ["@1.6::IRadio/slot1", "@1.6::IRadio/slot2"]:
        if instance not in af:
            errors.append("Missing radio HAL declaration: " + instance)

    samsung = manifests.get(SAMSUNG_RADIO_HIDL, {})
    sehs = samsung.get("interfaces", [])
    for hal_name, interface_name in [
        ("vendor.samsung.hardware.radio", "ISehRadio"),
        ("vendor.samsung.hardware.radio.bridge", "ISehBridge"),
    ]:
        supported = set()
        for h, i, instances in sehs:
            if h == hal_name and i == interface_name:
                supported.update(instances)
        if not {"slot1", "slot2"}.issubset(supported):
            errors.append("Incomplete Samsung radio declaration: " + hal_name)

    props = {}
    if (VENDOR / "build.prop").is_file():
        for line in (VENDOR / "build.prop").read_text(errors="replace").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                props.setdefault(k, []).append(v)
        if props.get("ro.hardware.chipname", [None])[-1] != "exynos8895":
            warnings.append(
                "Reported ro.hardware.chipname differs from Exynos 8895: investigate "
                "dependency/ROM spoofing before changing the property"
            )

    rc = (VENDOR / CAMERA_RC)
    camera_mount = (
        "mount none /vendor/etc/alice-test7/camera-feature.xml "
        "/system/cameradata/camera-feature.xml bind"
    )
    if rc.is_file() and camera_mount not in rc.read_text(errors="replace"):
        warnings.append("Test7 camera-feature bind mount is not present")
    if rc.is_file() and "ro.build.fingerprint=" in rc.read_text(errors="replace"):
        warnings.append("Camera feature mount depends on an exact system fingerprint")

    manifest_path = ROOT / "metadata/vendor-image-manifest.json"
    if manifest_path.exists():
        inventory = json.loads(manifest_path.read_text())
        for entry in inventory.get("entries", []):
            if entry.get("path") == "etc/init" and entry.get("mode") == 0:
                warnings.append(
                    "Baseline EROFS metadata marks /vendor/etc/init mode 0000; "
                    "verify runtime init parsing before changing baseline metadata"
                )
                break

    warnings.extend([
        "Dual slot HAL declarations do not prove concurrent LTE or VoLTE/VoWiFi",
        "Samsung Camera HAL metadata/preview must be verified with runtime logs; "
        "binary presence and HAL version alone are insufficient",
    ])
    report = {
        "device": "Samsung Galaxy S8+ dream2lte, Exynos 8895",
        "source": "Test7 vendor binary tree",
        "verification_scope": "offline_static_only",
        "flash_ready": False,
        "camera_fixed": False,
        "dual_lte_verified": False,
        "volte_vowifi_verified": False,
        "errors": errors,
        "warnings": warnings,
        "vendor_properties": {
            key: props.get(key, [])
            for key in [
                "ro.product.vendor.device",
                "ro.hardware.chipname",
                "ro.vendor.sec.radio.def_network",
                "ro.vendor.radio.default_network",
                "ro.vendor.epdg.support",
            ]
        },
        "hidl": manifests,
        "elf_dependencies": binaries,
    }
    output = Path(opts.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "audit_created": str(output),
        "errors": len(errors),
        "warnings": len(warnings),
        "scope": report["verification_scope"],
        "flash_ready": False,
    }, ensure_ascii=False))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
