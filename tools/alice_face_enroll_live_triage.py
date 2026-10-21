#!/usr/bin/env python3
"""Samsung Face enrollment failure triage: read-only / privacy-minimized.

Use --interactive, open Settings > Face recognition, retry enrollment, then
press Enter. The tool prints COUNTS ONLY, never raw log messages, face
templates, subscriber identity, photos, paths, or facial sensor data.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime

def cmd(*args: str, timeout=35) -> tuple[int,str]:
    p=subprocess.run(["adb","-d",*args],capture_output=True,text=True,
                     encoding="utf8",errors="replace",timeout=timeout)
    return p.returncode,p.stdout

CATEGORIES={
    "face_session_or_enroll_attempt":r"(?i)(?:faceprovider|faceservice|biometricsetting|semface|biometrics\.face|face.*hal).{0,160}(?:enroll|session|start|sensor)",
    "face_hardware_or_hal_failure":r"(?i)(?:faceprovider|faceservice|semface|biometrics\.face|face.*hal).{0,180}(?:exception|error|fail|invalid|unavailable|denied|dead|crash)",
    "biometric_app_failure":r"(?i)(?:biometricsetting|faceenroll|faceactivity|semfacemanager).{0,180}(?:exception|error|fail|denied|missing|crash)",
    "camera_device_busy_or_error":r"(?i)(?:cameraservice|cameradevice|cameraprovider|exynoscamera).{0,160}(?:busy|in use|error|fail|unavailable)",
    "face_permission_denied":r"(?i)(?:avc: denied|permission denial).{0,180}(?:face|biometric|camera)",
    "iris_framework_activity":r"(?i)(?:semiris|irisservice|irisscanner|irisenroll)",
}
COMPILED={k:re.compile(pattern) for k,pattern in CATEGORIES.items()}
EPOCH=re.compile(r"^\s*(\d{10})(?:\.(\d+))?\s+")

def classify(log:str,device_start:int)->dict:
    counts={k:0 for k in CATEGORIES}
    scanned=0
    used=0
    for line in log.splitlines():
        scanned+=1
        m=EPOCH.match(line)
        if not m:
            continue
        if int(m.group(1))<device_start-3:
            continue
        used+=1
        # Many logs have sensitive strings. Match in RAM only; never save/output.
        for name,pat in COMPILED.items():
            if pat.search(line):
                counts[name]+=1
    return {
      "device_start_epoch":device_start,
      "log_lines_scanned":scanned,
      "log_lines_in_observation_window":used,
      "event_counts":counts,
      "note":"0 errors is NOT evidence enrollment works; some HALs log nothing.",
      "raw_logs_exposed":False,
      "biometric_templates_exposed":False,
    }

def run(interactive:bool)->dict:
    code,epoch=cmd("shell","date","+%s")
    if code!=0 or not epoch.strip().isdigit():
        raise RuntimeError("adb device time unavailable; verify adb -d devices")
    started=int(epoch.strip())
    state={}
    for name,prop in (
        ("face_service_init","init.svc.sec-biometrics-face-aidl"),
        ("face_feature","ro.product.vendor.device"),
    ):
        _,v=cmd("shell","getprop",prop)
        state[name]=v.strip()[:96]
    _,sl=cmd("shell","service","list")
    state["face_aidl_registered"]= "android.hardware.biometrics.face.IFace/default" in sl
    _,features=cmd("shell","pm","list","features")
    state["iris_feature_advertised"]="android.hardware.biometrics.iris" in features
    state["face_feature_advertised"]="android.hardware.biometrics.face" in features
    if interactive:
        print("TRÊN ĐIỆN THOẠI: Mở Cài đặt > Sinh trắc học > Nhận diện khuôn mặt.")
        print("Thử bấm 'Đăng ký khuôn mặt' rồi quay lại Terminal và nhấn Enter.")
        try: input("Đã thử đăng ký? Nhấn Enter ... ")
        except EOFError: raise RuntimeError("Interactive requires a local keyboard")
    code,log=cmd("logcat","-d","-v","epoch","-b","main","-b","system","-t","12000",timeout=55)
    if code!=0:raise RuntimeError("Cannot read logcat; check ADB privileges")
    result=classify(log,started)
    result["runtime_state"]=state
    result["app_flow_user_reproduced"]=interactive
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interactive",action="store_true")
    p.add_argument("--output",type=str)
    p.add_argument("--selftest",action="store_true")
    a=p.parse_args()
    if a.selftest:
        sample="1760000000.234  123  123 E FaceService: createSession failed for hardware\n" \
               "1760000002.235  124  124 E CameraService: camera busy\n" \
               "1750000000.100  124  124 E FaceService: error outside window\n"
        d=classify(sample,1760000000)
        assert d["event_counts"]["face_hardware_or_hal_failure"]==1,d
        assert d["event_counts"]["camera_device_busy_or_error"]==1,d
        assert d["event_counts"]["face_session_or_enroll_attempt"]==1,d
        print("PASS: sanitized live Face enrollment counter logic")
        return
    try: report=run(a.interactive)
    except (RuntimeError,subprocess.TimeoutExpired) as e:
        p.exit(2,f"FACE_TRIAGE_ERROR: {e}\n")
    blob=json.dumps(report,indent=2,ensure_ascii=False)+"\n"
    if a.output:
        from pathlib import Path
        Path(a.output).expanduser().write_text(blob)
    print(blob)
if __name__=="__main__":main()
