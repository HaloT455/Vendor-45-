#!/usr/bin/env python3
"""Regression for real 2026-10-19 SamsungCamera crash, sanitized excerpts only."""
from camera_preview_contract import audit

# AOSP output stream size 1440x1080 independently observed in previous camera
# service captures; the October 19 user log confirmed the selected size.
SERVICE = """
android.scaler.availableStreamConfigurations (d000a): int32[8]
  [34 1440 1080 OUTPUT ]
  [33 3264 2448 OUTPUT ]
Dumping configured vendor tag descriptors: 9 entries
0x80000001 (liveHdrLevelRange) with type 1 (int32) defined in section samsung.android.control
"""
APP = """
10-19 23:37:21.604 E SemCameraCharacteristics:
 CameraCharacteristics.Key(samsung.android.scaler.availablePreviewStreamConfigurations) is not supported
10-19 23:37:21.604 W PreviewManager: calculatePreviewSurfaceSize : Not supported preview size!(1440x1080)
10-19 23:37:21.605 W PreviewManager: calculatePreviewSurfaceSize : Changed to optimal preview size!(null)
10-19 23:37:21.980 E AndroidRuntime: FATAL EXCEPTION: main
10-19 23:37:21.980 E AndroidRuntime: Process: com.sec.android.app.camera
10-19 23:37:21.980 E AndroidRuntime: java.lang.NullPointerException
 at com.sec.android.app.camera.preview.PreviewManagerImpl.changePreviewSurfaceSize
"""
r = audit(SERVICE, APP)
assert r["diagnosis"] == "SAMSUNG_VENDOR_PREVIEW_TAG_GAP", r
assert r["requested_size_advertised_in_aosp"], r
assert r["null_preview"] and r["preview_npe"] and r["samsung_preview_vendor_tag_reported_missing"], r
assert not r["runtime_fixed"] and not r["flash_ready"]
print("PASS: 19 October Samsung Camera immediate-close regression matches missing preview tag and null-size NPE.")
print("Note: offline fixture does not prove the new vendor loads or fixes app runtime.")
