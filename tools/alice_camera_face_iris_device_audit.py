#!/usr/bin/env python3
"""ALICE S8+ Android 16 read-only Camera/Face/Iris triage on the Zorin host.

Never reads or prints IMEI, IMSI, SIM data, enrolled biometric templates,
keyguard credentials, secure keys, or raw logcat. No su, no property writes.
The optional --launch-camera opens the Samsung Camera activity only; it does
NOT take a photo or claim shutter latency measurement.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path


def adb(*args: str, timeout=18) -> tuple[int, str]:
    p=subprocess.run(["adb", "-d", "shell", *args], text=True,
                     encoding="utf-8", errors="replace",
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     timeout=timeout, check=False)
    return p.returncode, p.stdout


def prop(name: str) -> str:
    _, val=adb("getprop", name)
    return val.strip()[:128]


def safe_device_audit(launch_camera=False) -> dict:
    result={
        "model":prop("ro.product.vendor.model"),
        "device":prop("ro.product.vendor.device"),
        "android_sdk":prop("ro.build.version.sdk"),
        "face_init_service":prop("init.svc.sec-biometrics-face-aidl"),
        "camera_provider_init_service":prop("init.svc.sec-camera-provider-4-0"),
        "fingerprint_init_service":prop("init.svc.vendor.samsung.hardware.biometrics.fingerprint@3.0-service"),
        "note":"Declared face HAL and a running init service do not prove sensor enrollment/authentication.",
    }
    _, feature_text=adb("pm", "list", "features")
    features=feature_text.lower().splitlines()
    result["face_feature_advertised"]=any("android.hardware.biometrics.face" in x for x in features)
    result["iris_feature_advertised"]=any("android.hardware.biometrics.iris" in x for x in features)
    result["fingerprint_feature_advertised"]=any("android.hardware.fingerprint" in x for x in features)
    _, services=adb("service", "list")
    result["face_aidl_binder_registered"]=bool(re.search(
        r"android\.hardware\.biometrics\.face\.IFace/default",services,re.I))
    result["iris_service_name_seen"]=any("iris" in x.lower()
                                         for x in services.splitlines())
    _, dumpsys_list=adb("dumpsys", "-l")
    result["face_dumpsys_available"]=bool(re.search(r"(?m)^\s*face\s*$",dumpsys_list))
    result["biometric_dumpsys_available"]=bool(re.search(r"(?m)^\s*biometric\s*$",dumpsys_list))
    _, face_dump=adb("dumpsys","face",timeout=30)
    result["face_sensor_properties_mentioned"]=bool(re.search(
        r"SensorProps|sensorProperties|sensorId|FaceSensor",face_dump,re.I))
    # Never write or display device dumps: they can include template IDs.
    _, logcat=adb("logcat","-b","main","-d","-t","1500", timeout=35)
    patterns={
        "camera_error_count":r"(?i)(?:Camera3-Device|CameraProvider|ALICE_CameraPreview).{0,100}(?:fatal|fail|error)",
        "face_error_count":r"(?i)(?:FaceService|FaceProvider|ISehFace|biometrics\.face).{0,100}(?:fatal|fail|error|denied|exception)",
        "iris_mention_count":r"(?i)(?:iris(?:service|scanner|daemon|sensor)|iriscamera)",
        "camera_vendor_tag_issue_count":r"(?i)(?:availablePreviewStreamConfigurations.{0,90}(?:not supported|missing)|Range min.{0,40}max)",
        "selinux_denied_biometrics_count":r"(?i)avc: denied.{0,200}(?:face|iris|biometric)",
    }
    result["recent_log_counters"]={
        key:sum(bool(re.search(pattern,line)) for line in logcat.splitlines())
        for key,pattern in patterns.items()
    }
    result["log_sample_max_lines"]=1500
    result["raw_logs_saved"]=False
    result["raw_biometrics_data_saved"]=False
    if launch_camera:
        code,out=adb("am", "start", "-W",
                     "-a", "android.media.action.STILL_IMAGE_CAMERA",
                     "-p", "com.sec.android.app.camera", timeout=35)
        m=re.search(r"(?m)^\s*TotalTime:\s*(\d+)\s*$",out)
        result["camera_activity_launch_success"]=code==0 and m is not None
        result["camera_activity_start_total_ms"]=int(m.group(1)) if m else None
        result["camera_time_note"]="Android Activity start only; NOT preview-ready or shutter-to-JPEG latency"
    result["face_unlock_verified"]=False
    result["iris_unlock_verified"]=False
    result["capture_shutter_latency_verified"]=False
    return result


def selftest():
    assert re.search(r"android\.hardware\.biometrics\.face\.IFace/default",
                     "23 android.hardware.biometrics.face.IFace/default [xx]")
    assert not re.search(r"android\.hardware\.biometrics\.face\.IFace/default",
                         "nothing here")
    assert re.search(r"(?m)^\s*TotalTime:\s*(\d+)\s*$",
                     "Status: ok\nTotalTime: 764\n")
    print("PASS: service matching and camera activity timing parser")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--launch-camera",action="store_true",
                   help="Open Samsung Camera once; measures Activity start ONLY")
    p.add_argument("--output",type=Path,
                   help="Optional sanitized JSON report; no raw logs saved")
    p.add_argument("--selftest",action="store_true")
    a=p.parse_args()
    if a.selftest:
        selftest()
        return
    if not shutil.which("adb"):
        p.error("adb not installed or unavailable")
    try:
        report=safe_device_audit(a.launch_camera)
    except subprocess.TimeoutExpired as exc:
        p.error("ADB timed out: "+str(exc.cmd[:2]))
    result=json.dumps(report,indent=2,ensure_ascii=False)+"\n"
    if a.output:
        a.output.write_text(result)
        print("SAFE_REPORT_WRITTEN",a.output)
    print(result)


if __name__=="__main__":
    main()
