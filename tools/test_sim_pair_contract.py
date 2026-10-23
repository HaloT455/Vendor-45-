#!/usr/bin/env python3
"""One-UI8 Galaxy S8+ R16 + Camera/Video6 vendor offline pair gate.

CI compares exact kernel modem/Kconfig selections against the owner's known
working reference and rejects accidental camera/radio regressions. Does not
assert that newly paired boot and vendor have booted on physical hardware.
"""
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODEM_OPTIONS = (
    "CONFIG_SOC_EXYNOS8895=y",
    "CONFIG_SEC_SIPC_MODEM_IF=y",
    "CONFIG_SEC_MODEM_SS310AP=y",
    "CONFIG_UMTS_MODEM_SS310AP=y",
    "CONFIG_LINK_DEVICE_SHMEM=y",
    "CONFIG_LINK_DEVICE_NAPI=y",
    "CONFIG_SHM_IPC=y",
    "CONFIG_MODEM_IF_QOS=y",
    "CONFIG_EROFS_FS=y",
)
KERNEL_POLICY = "CONFIG_CPU_FREQ_DEFAULT_GOV_ENERGYSTEP=y"
EXPECTED_CAMERA = "work/a16-shutter-lag-photo-fast-feature-gate"
TEXT_REFERENCE_SHA = {
    "etc/init/init.vendor.rilcommon.rc": "c61001ec4a485b436c99fb2d55786aabd92d6fc9f5e4b1b9beff458eb31be610",
    "etc/init/vendor.sem.rilchip.rc": "f3e6eb2e5330a3ba5e1a650ca6fc39b0b9ba25b9843743b7da8f15632a83380f",
    "etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml": "f7d0dfced1b52feb24202d9d8ce1e179dfd67f4c57d42081f57171da03922f2f",
    "etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml": "ad87982c72367cea3f368a023db52ef9a0b7da512d2b9689db8e3ccd89987afe",
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kernel-root", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    errors, warnings = [], []
    config = (args.kernel_root / "arch/arm64/configs/exynos8895-dream2lte_defconfig").read_text().splitlines()
    for key in MODEM_OPTIONS + (KERNEL_POLICY,):
        if config.count(key) != 1:
            errors.append("Kernel mismatch: " + key)

    props = (ROOT / "vendor/build.prop").read_text().splitlines()
    for key in ("ro.product.vendor.device=dream2lte", "ro.telephony.default_network=9,9", "ro.radio.noril=no"):
        matches = props.count(key)
        if matches < 1 or (key.startswith("ro.telephony.default_network=") and matches != 1):
            errors.append("Vendor property missing or ambiguous: " + key)
        propname = key.split("=", 1)[0] + "="
        if any(row.startswith(propname) and row != key for row in props):
            errors.append("Vendor property conflicting values: " + propname[:-1])
    init = (ROOT / "vendor/etc/init/init.vendor.rilcommon.rc").read_text()
    if "exec_start network_config" not in init:
        errors.append("Samsung NetworkConfig boot hook missing")
    if "setprop ro.telephony.default_network ${ro.vendor.radio.default_network}" in init:
        warnings.append("Owner-reference late ro.* setprop may be rejected by Android16 property service; no guarantee of runtime benefit")

    for rel, digest in TEXT_REFERENCE_SHA.items():
        file = ROOT / "vendor" / rel
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            errors.append("Working-reference radio metadata changed: " + rel)

    cam = (ROOT / "tools/native_camera/alice_preview_bridge.c").read_text()
    if "#define VIDEO_FIELDS 6" not in cam or "add(merged,VIDEO_TAG,video_config,video_n*VIDEO_FIELDS)" not in cam:
        errors.append("Samsung Camera Video6 bridge changed")
    for rel in ("bin/hw/rild", "bin/secril_config_svc", "lib64/libril_sem.so", "lib64/libsec-ril.so"):
        if not (ROOT / "vendor" / rel).is_file():
            errors.append("Legacy Samsung RIL binary missing: " + rel)

    manifest = ET.parse(ROOT / "vendor/etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml").getroot()
    fq = {(x.text or "").strip() for x in manifest.iter("fqname")}
    if not {"@1.6::IRadio/slot1", "@1.6::IRadio/slot2"}.issubset(fq):
        errors.append("Two HIDL IRadio services not declared")
    result = {
        "pair_id": "ALICE-S8P-A16-R16-SIMCAM-20261023",
        "reference": "owner-supplied boot.img and vendor.new.dat.br",
        "kernel_modem_options_checked": len(MODEM_OPTIONS),
        "camera_video6_contract": "present" if not any("Video6" in e for e in errors) else "FAIL",
        "sim_registration_on_device": "NOT_TESTED",
        "camera_video_on_device": "NOT_TESTED",
        "safe_to_flash": False,
        "status": "PASS_OFFLINE" if not errors else "FAIL",
        "warnings": warnings,
        "errors": errors,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded)
    if errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
