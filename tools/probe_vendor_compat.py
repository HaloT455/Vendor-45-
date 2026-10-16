#!/usr/bin/env python3
"""Analyze Camera/RIL Test7 ELF ABI surfaces; never flash or rewrite blobs.

No Android SDK headers are assumed. Run on Linux x86-64:
  python3 tools/probe_vendor_compat.py --output out/compat.json

This is a forensic report. An ELF symbol, HIDL entry or string is NOT evidence
that Samsung Camera works or that the baseband supports dual active LTE.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
CAMERA = [
    "lib/hw/camera.universal8895.so",
    "lib64/hw/camera.universal8895.so",
    "lib/libexynoscamera.so",
    "lib64/libexynoscamera.so",
    "lib/libexynoscamera3.so",
    "lib64/libexynoscamera3.so",
    "lib/libshim_camera.so",
    "lib64/libshim_camera.so",
    "lib/libcamera_shim.so",
    "lib64/libcamera_shim.so",
    "lib/vendor.samsung.hardware.camera.provider@4.0.so",
    "lib64/vendor.samsung.hardware.camera.provider@4.0.so",
    "bin/hw/vendor.samsung.hardware.camera.provider@4.0-service",
]
RADIO = [
    "bin/hw/rild",
    "lib64/libsec-ril.so",
    "lib64/libril_sem.so",
    "lib64/vendor.samsung.hardware.radio@2.2.so",
    "lib64/vendor.samsung.hardware.radio.bridge@2.0.so",
    "lib64/android.hardware.radio@1.6.so",
]
SONAME_DIRS = ["lib", "lib64", "lib/hw", "lib64/hw"]
CAMERA_NEEDLES = [
    b"get_vendor_tag_ops",
    b"HAL_MODULE_INFO_SYM",
    b"availablePictureStreamConfigurations",
    b"availableFullPictureStreamConfigurations",
    b"camera3_device_ops",
    b"configure_streams",
    b"process_capture_request",
]
RADIO_NEEDLES = [
    b"getRadioCapability", b"setRadioCapability",
    b"responseRadioCapability", b"REQUEST_NOT_SUPPORTED",
    b"GET_RADIO_CAPABILITY", b"SET_RADIO_CAPABILITY",
    b"DsDsLTEOperatingStack",
]


def run_readelf(path: Path, option: str) -> str:
    cp = subprocess.run(
        ["readelf", option, "--wide", str(path)],
        text=True, capture_output=True, check=True, timeout=45
    )
    return cp.stdout


def elf_info(path: Path, needles: list[bytes]) -> dict:
    data = path.read_bytes()
    if data[:4] != b"\\x7fELF":
        raise ValueError(f"not ELF: {path}")
    hdr = run_readelf(path, "-h")
    dyn = run_readelf(path, "-d")
    symbols = run_readelf(path, "-Ws")
    kinds = sorted(set(re.findall(r"\\(NEEDED\\).*?\\[([^\\]]+)\\]", dyn)))
    sonames = sorted(set(re.findall(r"\\(SONAME\\).*?\\[([^\\]]+)\\]", dyn)))
    unresolved = sorted(set(
        match.group(1).split("@")[0]
        for line in symbols.splitlines()
        if (match := re.search(r"\\bUND\\s+([^\\s]+)", line)) and match.group(1) != "0"
    ))
    exports = sorted(set(
        match.group(1).split("@")[0]
        for line in symbols.splitlines()
        if not re.search(r"\\bUND\\s+", line)
        and (match := re.search(r"\\b(?:GLOBAL|WEAK)\\s+\\w+\\s+\\w+\\s+([^\\s]+)$", line))
    ))
    clazz = re.search(r"^\\s*Class:\\s*(.*)$", hdr, re.M)
    machine = re.search(r"^\\s*Machine:\\s*(.*)$", hdr, re.M)
    matches = {n.decode(): (n in data) for n in needles}
    return {
        "size": len(data),
        "class": clazz.group(1).strip() if clazz else "unknown",
        "machine": machine.group(1).strip() if machine else "unknown",
        "dt_needed": kinds,
        "soname": sonames,
        "undefined_symbols": len(unresolved),
        "exported_symbols": len(exports),
        "camera_hal_module_exported": "HAL_MODULE_INFO_SYM" in exports,
        "weak_symbol_candidates": [x for x in exports if "camera" in x.lower()][:40],
        "probe_strings": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="out/compat.json")
    args = parser.parse_args()
    catalog = {}
    for d in SONAME_DIRS:
        folder = VENDOR / d
        if folder.exists():
            for p in folder.glob("*.so"):
                catalog.setdefault(p.name, []).append(str(p.relative_to(VENDOR)))
    paths = {"camera": CAMERA, "radio": RADIO}
    probes, errors, warnings = {}, [], []
    for category, candidates in paths.items():
        for name in candidates:
            p = VENDOR / name
            if not p.is_file():
                warnings.append("not present: " + name)
                continue
            try:
                probes[name] = elf_info(
                    p, CAMERA_NEEDLES if category == "camera" else RADIO_NEEDLES
                )
                probes[name]["resolved_vendor_library_candidates"] = {
                    so: catalog[so] for so in probes[name]["dt_needed"] if so in catalog
                }
                probes[name]["unresolved_in_vendor_catalog"] = [
                    so for so in probes[name]["dt_needed"] if so not in catalog
                ]
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                errors.append(f"{name}: {exc}")

    primary = [
        "lib/hw/camera.universal8895.so",
        "lib64/hw/camera.universal8895.so",
    ]
    for name in primary:
        if name in probes and not probes[name]["camera_hal_module_exported"]:
            warnings.append(
                f"{name} lacks exported HAL_MODULE_INFO_SYM; check stripped/dynamic symbols"
            )
    for name, data in probes.items():
        if name.endswith("camera.universal8895.so"):
            if "HAL_MODULE_INFO_SYM" not in data["probe_strings"]:
                warnings.append(f"camera HAL signature absent from blob: {name}")

    radio_manifest = VENDOR / "etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml"
    hids = []
    if radio_manifest.is_file():
        for hal in ElementTree.parse(radio_manifest).getroot().iter("hal"):
            hids.append({
                "hal": hal.findtext("name"),
                "fqnames": [v.text for v in hal.findall("fqname")],
            })

    result = {
        "device": "Galaxy S8+ Exynos8895 dream2lte",
        "inspection": "ELF ABIs; complete runtime boot/camera/modem tests not performed",
        "camera_hal_upgraded": False,
        "simultaneous_dual_lte_enabled": False,
        "flash_ready": False,
        "probe_results": probes,
        "radio_hidl": hids,
        "errors": errors,
        "warnings": warnings + [
            "Unresolved-in-vendor DT_NEEDED can be satisfied by VNDK/APEX/system; not automatically an error",
            "Camera vendor tag strings are not a substitute for get_vendor_tag_ops descriptor registration",
            "RIL HIDL slot1+slot2 does not establish independent LTE baseband stacks",
            "Samsung proprietary camera framework lives outside vendor tree; Android 16 framework inputs needed",
            "CP firmware previously showed LTE-other-stack rejection path; no CP patch is included",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "report": str(out),
        "examined_elf": len(probes),
        "errors": len(errors),
        "warnings": len(result["warnings"]),
        "camera_hal_upgraded": False,
        "simultaneous_dual_lte_enabled": False,
        "flash_ready": False,
    }))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
