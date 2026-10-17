#!/usr/bin/env python3
"""Check Samsung Camera preview vendor-tag contract from sanitized ADB dumps.

This is a read-only regression guard for Galaxy S8+ Exynos8895.
AOSP camera stream support does NOT imply Samsung-specific vendor-tag support.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

VENDOR_PREVIEW = "samsung.android.scaler.availablePreviewStreamConfigurations"
AOSP_PREVIEW = "android.scaler.availableStreamConfigurations"


def audit(service: str, log: str) -> dict:
    count = re.search(r"Dumping configured vendor tag descriptors: (\d+) entries", service)
    tags = re.findall(r"0x[0-9a-fA-F]{8} \(([^)]+)\).*?defined in section ([A-Za-z0-9._]+)", service)
    vendor_keys = {section + "." + name for name, section in tags}
    aosp = []
    # Scope the check to format 34 IMPLEMENTATION_DEFINED, not arbitrary unsupported streams.
    for fmt, width, height in re.findall(
        r"\[\s*(\d+)\s+(\d+)\s+(\d+)\s+OUTPUT\s*\]", service
    ):
        if int(fmt) == 34:
            aosp.append([int(width), int(height)])
    requested = re.search(r"Not supported preview size!\((\d+)x(\d+)\)", log)
    requested_size = [int(requested.group(1)), int(requested.group(2))] if requested else None
    missing = (
        f"CameraCharacteristics.Key({VENDOR_PREVIEW}) is not supported" in log
    )
    null_preview = "Changed to optimal preview size!(null)" in log
    npe = (
        "java.lang.NullPointerException" in log
        and "PreviewManagerImpl.changePreviewSurfaceSize" in log
    )
    return {
        "vendor_tag_count": int(count.group(1)) if count else None,
        "samsung_preview_vendor_tag_registered": VENDOR_PREVIEW in vendor_keys,
        "samsung_preview_vendor_tag_reported_missing": missing,
        "standard_camera2_impl_defined_sizes": sorted(set(tuple(x) for x in aosp)),
        "requested_preview_size": requested_size,
        "requested_size_advertised_in_aosp": (
            requested_size is not None and tuple(requested_size) in set(map(tuple, aosp))
        ),
        "null_preview": null_preview,
        "preview_npe": npe,
        "diagnosis": (
            "SAMSUNG_VENDOR_PREVIEW_TAG_GAP" if
            missing and null_preview and npe and requested_size is not None
            and tuple(requested_size) in set(map(tuple, aosp))
            else "NOT_CONFIRMED"
        ),
        "remediation_scope": "vendor tag registration + actual static camera metadata, or app fallback",
        "runtime_fixed": False,
        "flash_ready": False,
    }


def selftest():
    import unittest

    class ContractTests(unittest.TestCase):
        service = """
== Camera Provider HAL legacy/0-0 (v2.6) ==
android.scaler.availableStreamConfigurations (d000a): int32[8]
[34 1440 1080 OUTPUT ]
[34 1920 1080 OUTPUT ]
Dumping configured vendor tag descriptors: 9 entries
0x80000001 (liveHdrLevelRange) with type 1 (int32) defined in section samsung.android.control
"""
        crash = """
SemCameraCharacteristics: UnsupportedOperationException - CameraCharacteristics.Key(samsung.android.scaler.availablePreviewStreamConfigurations) is not supported
PreviewManager: Not supported preview size!(1440x1080)
PreviewManager: Changed to optimal preview size!(null)
AndroidRuntime: java.lang.NullPointerException
at com.sec.android.app.camera.preview.PreviewManagerImpl.changePreviewSurfaceSize
"""
        def test_detect_specific_preview_tag_crash(self):
            result = audit(self.service, self.crash)
            self.assertEqual(result["diagnosis"], "SAMSUNG_VENDOR_PREVIEW_TAG_GAP")
            self.assertTrue(result["requested_size_advertised_in_aosp"])
            self.assertFalse(result["samsung_preview_vendor_tag_registered"])
        def test_no_false_claim_without_crash(self):
            result = audit(self.service, "")
            self.assertEqual(result["diagnosis"], "NOT_CONFIRMED")
        def test_no_false_claim_without_advertised_size(self):
            result = audit(self.service.replace("1440 1080", "1280 720"), self.crash)
            self.assertEqual(result["diagnosis"], "NOT_CONFIRMED")
        def test_missing_name_does_not_equal_added_metadata(self):
            result = audit(
                self.service + "0x80030000 (availablePreviewStreamConfigurations)"
                + " with type 1 (int32) defined in section samsung.android.scaler",
                self.crash)
            self.assertTrue(result["samsung_preview_vendor_tag_registered"])
            # Registration alone does not prove a static per-camera metadata value.
            self.assertFalse(result["runtime_fixed"])

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--camera-service", type=Path)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--selftest", action="store_true")
    opts = ap.parse_args()
    if opts.selftest:
        selftest()
        return
    if not opts.camera_service or not opts.log:
        ap.error("Provide both --camera-service and --log, or --selftest")
    report = audit(opts.camera_service.read_text(errors="replace"),
                   opts.log.read_text(errors="replace"))
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if opts.output:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(payload)
    else:
        print(payload)
    if report["diagnosis"] == "SAMSUNG_VENDOR_PREVIEW_TAG_GAP":
        print("CONFIRMED INCOMPATIBILITY. DO NOT CLAIM FIXED OR FLASH-READY.")


if __name__ == "__main__":
    main()
