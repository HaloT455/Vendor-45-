#!/usr/bin/env python3
"""Whole-vendor Android 16 compatibility inventory (READ ONLY).

VNDK was deprecated starting with Android 15: no VNDK v36 upgrade exists.
This audits an Exynos8895 Android-13-era vendor tree against a modern
Android 16 framework WITHOUT changing API levels, native blobs or VINTF.
"""
from __future__ import annotations
import argparse
import collections
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_PATHS = (
    "vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service",
    "vendor/lib64/libFaceService.so",
    "vendor/bin/hw/vendor.samsung.hardware.camera.provider@4.0-service",
    "vendor/bin/hw/android.hardware.media.omx@1.0-service",
    "vendor/bin/hw/samsung.software.media.c2@1.0-service",
    "vendor/lib64/omx/libOMX.Exynos.AVC.Encoder.so",
    "vendor/lib64/omx/libOMX.Exynos.HEVC.Encoder.so",
    "vendor/etc/media_codecs.xml",
    "vendor/etc/media_profiles_V1_0.xml",
    "vendor/etc/vintf/manifest/face-default-sec.xml",
    "vendor/etc/init/face-default-sec.rc",
)
NEEDED_RE = re.compile(r"\(NEEDED\).*?\[(.*?)\]")
VNDK_VERSION_RE = re.compile(r"^\d+$")


def parse_props(value: str) -> dict[str, str]:
    props = {}
    for row in value.splitlines():
        if "=" in row and not row.lstrip().startswith("#"):
            k, v = row.split("=", 1)
            props[k.strip()] = v.strip()
    return props


def require_version_sanity(properties: dict[str, str]) -> list[str]:
    errors = []
    vndk = properties.get("ro.vndk.version", "")
    # The old vendor must retain its actual VNDK version: version 36 is not
    # shipped as an Android 16 VNDK APEX and breaks the legacy linker contract.
    if vndk and VNDK_VERSION_RE.fullmatch(vndk) and int(vndk) >= 35:
        errors.append(
            "INVALID_VNDK: ro.vndk.version>=35; Android 15+ deprecated VNDK."
        )
    sdk = properties.get("ro.vendor.build.version.sdk", "")
    if sdk and VNDK_VERSION_RE.fullmatch(sdk) and int(sdk) >= 36 and vndk in {"33", "34"}:
        errors.append(
            "MISLEADING_VENDOR_SDK: SDK36 claimed while legacy VNDK remains; "
            "a property change does not rebuild native HAL libraries."
        )
    return errors


def metadata(root: Path) -> dict:
    p = parse_props((root / "vendor/build.prop").read_text(errors="replace"))
    manifest = ET.parse(root / "vendor/etc/vintf/manifest.xml").getroot()
    matrix = ET.parse(root / "vendor/etc/vintf/compatibility_matrix.xml").getroot()
    for v in (manifest, matrix):
        if v.get("type") != "device":
            raise ValueError("Unexpected device VINTF document type")
    def xtext(xroot, tag):
        el = xroot.find(tag)
        return el.text.strip() if el is not None and el.text else None
    face = []
    for f in (root / "vendor/etc/vintf").rglob("*.xml"):
        try:
            xtree = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for hal in xtree.findall("hal"):
            if hal.findtext("name") == "android.hardware.biometrics.face":
                face.append({
                    "path":str(f.relative_to(root)),
                    "format":hal.get("format"),
                    "version":hal.findtext("version"),
                    "fqname":hal.findtext("fqname"),
                })
    # AIDLv2 declarations are not evidence of a functioning unlock service.
    return {
        "vendor_build_sdk":p.get("ro.vendor.build.version.sdk"),
        "vendor_release":p.get("ro.vendor.build.version.release"),
        "legacy_vndk_version":p.get("ro.vndk.version"),
        "vendor_device":p.get("ro.product.vendor.device"),
        "first_api_level":p.get("ro.product.first_api_level"),
        "soc_model":p.get("ro.soc.model"),
        "potentially_inconsistent_chipname":p.get("ro.hardware.chipname"),
        "vintf_target_level":manifest.get("target-level"),
        "vintf_sepolicy_version":xtext(manifest,"sepolicy/version"),
        "vintf_vendor_ndk":xtext(matrix,"vendor-ndk/version"),
        "face_hal_manifest_declarations":face,
        "version_contract_errors":require_version_sanity(p),
    }


def inventory_native(root: Path) -> dict:
    native = []
    symlink_count = 0
    for f in (root / "vendor").rglob("*"):
        if f.is_symlink():
            symlink_count += 1
            continue
        if not f.is_file():
            continue
        try:
            with f.open("rb") as stream:
                hdr=stream.read(8)
        except OSError:
            continue
        if hdr[:4] != b"\x7fELF":
            continue
        native.append((f, 32 if hdr[4] == 1 else 64 if hdr[4] == 2 else 0))
    names = {32:set(),64:set()}
    for file, bitness in native:
        if bitness in names and "/lib" in file.as_posix():
            names[bitness].add(file.name)
    external = collections.Counter()
    native_by_bitness = collections.Counter()
    inspect_errors = []
    related = {"camera":[],"video":[],"face":[]}
    camera_pattern=re.compile(r"camera|exynos|vdis|vision",re.I)
    video_pattern=re.compile(r"media|codec|omx|c2|mfc",re.I)
    face_pattern=re.compile(r"biometric|face|authfw",re.I)
    inspected = []
    for file,bitness in native:
        path=file.relative_to(root).as_posix()
        native_by_bitness[str(bitness)]+=1
        run=subprocess.run(["readelf","-d","--wide",str(file)],capture_output=True,
                           text=True,errors="replace")
        if run.returncode and "There is no dynamic section" not in run.stderr:
            inspect_errors.append({"path":path,"stderr":run.stderr[-240:]})
        needed=NEEDED_RE.findall(run.stdout)
        inherited=set(names.get(bitness,set()))
        missing_from_vendor=sorted(set(needed)-inherited)
        external.update(missing_from_vendor)
        entry={"path":path,"abi":bitness,"needed":sorted(set(needed)),
               "external_to_vendor":missing_from_vendor}
        inspected.append(entry)
        for kind, pat in [("camera",camera_pattern),("video",video_pattern),("face",face_pattern)]:
            if pat.search(path):
                related[kind].append(entry)
    required={p:(root/p).is_file() for p in PROTECTED_PATHS}
    return {
        "native_elf_count":len(native),
        "abi_counts":dict(native_by_bitness),
        "symlinks":symlink_count,
        "native_inspection_errors":inspect_errors,
        "existing_runtime_payloads":required,
        "missing_critical_payloads":[p for p,ok in required.items() if not ok],
        "external_dependency_names":dict(sorted(external.items(), key=lambda x:(-x[1],x[0]))),
        "external_not_automatically_broken":True,
        "camera_stack":related["camera"],
        "video_stack":related["video"],
        "face_stack":related["face"],
        "all_elf_dependencies":inspected,
    }


def make_report(root:Path) -> dict:
    md=metadata(root)
    binaries=inventory_native(root)
    return {
        "project":"ALICE / Samsung Galaxy S8+ dream2lte Exynos8895",
        "framework_sdk_target":36,
        "requested_vndk":36,
        "vndk_36_exists":False,
        "legacy_vndk_supported_on_android16":True,
        "safe_upgrade_strategy":"Keep honest legacy VNDK 33; audit and selectively port ABI/HAL to Android 16.",
        "metadata":md,
        "native":binaries,
        "blocking_issues":md["version_contract_errors"] + [
           "MISSING_VENDOR_PAYLOAD: "+p for p in binaries["missing_critical_payloads"]
        ],
        "validation_gates_not_run":[
           "Android16 live linker/dlopen and VINTF runtime",
           "Samsung Camera 30s photo + video recording and playback",
           "Face AIDL registration + enrollment + unlock",
           "RIL dual LTE, IMS, audio, graphics, Wi-Fi, SELinux after boot",
           "hardware VTS/CTS and recoverable flashing"
        ],
        "vendor_sdk_changed":False,
        "native_hal_rebuilt":False,
        "android16_fully_compatible_verified":False,
        "flash_ready":False,
    }


def selftest():
    p=parse_props("ro.vndk.version=33\nro.vendor.build.version.sdk=33\n#ro.vndk.version=36\n")
    assert p["ro.vndk.version"]=="33",p
    assert not require_version_sanity(p)
    assert any("INVALID_VNDK" in x for x in require_version_sanity({"ro.vndk.version":"36"}))
    assert any("MISLEADING_VENDOR_SDK" in x for x in require_version_sanity(
        {"ro.vndk.version":"33","ro.vendor.build.version.sdk":"36"}))
    assert NEEDED_RE.findall("0x1 (NEEDED) Shared library: [libcamera_client.so]")==["libcamera_client.so"]
    print("PASS 4/4 vendor-API contract regression tests")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--output",type=Path,default=Path("out/android16-vendor-abi-audit.json"))
    p.add_argument("--selftest",action="store_true")
    args=p.parse_args()
    if args.selftest:
        selftest()
        return
    report=make_report(args.root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    summary={"native_elf":report["native"]["native_elf_count"],
             "abi_counts":report["native"]["abi_counts"],
             "legacy_vndk":report["metadata"]["legacy_vndk_version"],
             "vendor_sdk":report["metadata"]["vendor_build_sdk"],
             "vintf":report["metadata"]["vintf_target_level"],
             "media_video_paths":len(report["native"]["video_stack"]),
             "camera_paths":len(report["native"]["camera_stack"]),
             "face_paths":len(report["native"]["face_stack"]),
             "blockers":report["blocking_issues"],
             "flash_ready":False,"output":str(args.output)}
    print(json.dumps(summary,indent=2))
    if report["blocking_issues"] or report["native"]["native_inspection_errors"]:
        raise SystemExit("ABI audit found structural blockers or invalid ELF files")


if __name__ == "__main__":
    main()
