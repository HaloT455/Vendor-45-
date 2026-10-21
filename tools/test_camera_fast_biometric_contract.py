#!/usr/bin/env python3
"""Static regression guard for CAMERA metadata fast path, Samsung FACE AIDL and IRIS gaps.

CI is not proof of faster physical shutter or successful biometric enrollment.
Never replace real lockscreen biometrics with a fake/virtual authenticator.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"tools/native_camera/alice_preview_bridge.c"
RC=ROOT/"vendor/etc/init/face-default-sec.rc"
XML=ROOT/"vendor/etc/vintf/manifest/face-default-sec.xml"
CAMPROV=ROOT/"vendor/etc/init/vendor.samsung.hardware.camera.provider@4.0-service.rc"
FACE_BIN=ROOT/"vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service"


def analyze(root: Path = ROOT) -> dict:
    src=(root/"tools/native_camera/alice_preview_bridge.c").read_text()
    rc=(root/"vendor/etc/init/face-default-sec.rc").read_text()
    xml=(root/"vendor/etc/vintf/manifest/face-default-sec.xml").read_text()
    cp=(root/"vendor/etc/init/vendor.samsung.hardware.camera.provider@4.0-service.rc").read_text()
    assert "#define VIDEO_FIELDS 6" in src
    assert "add(merged,VIDEO_TAG,video_config,video_n*VIDEO_FIELDS)" in src
    assert "static_metadata[MAX_CAMERAS]" in src
    assert src.count("__atomic_store_n(&static_metadata[id],cached,__ATOMIC_RELEASE)") == 1
    assert src.count("__atomic_load_n(&static_metadata[id],__ATOMIC_ACQUIRE)") == 1
    assert "if(!cached) {\n        pthread_mutex_lock(&mu);" in src
    assert "if(!cached && prepare_ops())" in src
    assert "cached=augment(info->static_camera_characteristics);" in src
    assert "info->static_camera_characteristics=cached;" in src
    assert "delegate->get_camera_info(id,info)" in src
    assert "video_config[pos+2]=VIDEO_FPS;" in src
    assert "video_config[pos+3]=VIDEO_FPS;" in src
    assert "ioprio rt 4" in cp and "CameraServiceCapacity" in cp
    assert "service sec-biometrics-face-aidl" in rc
    assert "/vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service" in rc
    assert "<name>android.hardware.biometrics.face</name>" in xml
    assert "<version>2</version>" in xml
    assert "<fqname>IFace/default</fqname>" in xml
    face_bin=root/"vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service"
    assert face_bin.is_file(), "AIDL face service binary missing"
    assert (root/"vendor/lib64/android.hardware.biometrics.face-V2-ndk.so").is_file()
    vendor=root/"vendor"
    # Filename inventory is insufficient to prove that firmware iris drivers
    # and framework apps are absent: clearly label this as a vendor FILE gap.
    iris_named=[p.relative_to(vendor).as_posix()
                for p in vendor.rglob("*") if "iris" in p.name.lower()]
    result={
        "camera_bridge_atomic_metadata_cache":True,
        "camera_legacy_get_info_still_called":True,
        "video_six_int_unchanged":True,
        "camera_hal_existing_performance_profile_unchanged":True,
        "face_aidl_declared":True,
        "face_service_binary_present":True,
        "face_hal_operational_on_device":None,
        "face_enrollment_or_unlock_verified":False,
        "iris_named_vendor_files":iris_named[:25],
        "iris_driver_or_service_operational_on_device":None,
        "camera_open_or_shutter_latency_measured":False,
        "vendor_image_safe_to_flash":False,
        "requires_device_log_and_latency_check":True,
    }
    return result


def main():
    r=analyze()
    print(json.dumps(r,indent=2))
    print("PASS: immutable camera metadata cache contract; Face/Iris do not claim operational")
if __name__=="__main__":
    main()
