#!/usr/bin/env python3
"""Post-flash Samsung Camera regression classifier (adb read-only + app relaunch).

This is a lightweight script for the user's Zorin OS system.
Run while the Galaxy S8+ is booted after flashing the vendor trial:
  python3 tools/diagnose_postflash_samsungcamera.py
"""
import argparse
import datetime
import re
import subprocess
import time
from pathlib import Path
PKG="com.sec.android.app.camera"
def adb(*args):
    p=subprocess.run(["adb","-d",*args],text=True,capture_output=True,timeout=40)
    return p.stdout + p.stderr
def run():
    a=argparse.ArgumentParser()
    a.add_argument("--output",type=Path)
    x=a.parse_args()
    d=x.output or Path.home()/"Downloads"/("ALICE_CAM_AFTER_FLASH_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    d.mkdir(parents=True,exist_ok=True)
    def save(filename,*args):
        data=adb(*args)
        (d/filename).write_text(data)
        return data
    if adb("get-state").strip()!="device":raise SystemExit("ADB device unavailable")
    print("Collecting runtime vendor tag descriptor and Samsung Camera permissions (READ ONLY)")
    service=save("media_camera_PRIVATE.txt","shell","dumpsys","media.camera")
    pkg=save("samsung_package_PRIVATE.txt","shell","dumpsys","package",PKG)
    version=save("version.txt","shell","getprop","ro.telephony.default_network")
    bridge=save("camera_bridge_paths.txt","shell","su","-c",
        "ls -l /vendor/lib*/hw/camera.*universal8895.so 2>&1; sha256sum /vendor/lib*/hw/camera.universal8895.so 2>&1")
    adb("shell","am","force-stop",PKG)
    save("launch.txt","shell","monkey","-p",PKG,"-c","android.intent.category.LAUNCHER","1")
    time.sleep(8)
    pid=save("pid_after.txt","shell","pidof",PKG).strip()
    exit_info=save("exit_info_PRIVATE.txt","shell","dumpsys","activity","exit-info",PKG)
    logs=save("logcat_PRIVATE.txt","logcat","-d","-b","main,system,crash","-v","threadtime","-t","16000")
    keys=[
        "availablePreviewStreamConfigurations","availablePictureStreamConfigurations",
        "availableVideoConfigurations","PreviewManagerImpl.changePreviewSurfaceSize",
        "ACCESS_SYSTEM_KEY_DISPATCHING","onStartPreviewCompleted",
        "AndroidRuntime: FATAL EXCEPTION","AndroidRuntime: Process: com.sec.android.app.camera",
        "AndroidRuntime: java.lang.","CameraWindowManager","MediaRecorder",
        "Fatal signal","CameraService: binderDied","ExynosCamera",
    ]
    lines=logs.splitlines()
    idx={j for i,l in enumerate(lines) if any(k.lower() in l.lower() for k in keys)
         for j in range(max(0,i-1),min(len(lines),i+7))}
    redacted="\n".join(f"{i+1}: {lines[i]}" for i in sorted(idx)[-200:])
    (d/"camera_crash_filtered_REVIEW_BEFORE_SHARING.txt").write_text(redacted+"\n")
    matches=list(re.finditer(r"FATAL EXCEPTION:",logs))
    crash=""
    for match in matches:
        candidate=logs[match.start():match.start()+2500]
        if "Process: "+PKG in candidate[:500]:crash=candidate
    permission_error="Requires ACCESS_SYSTEM_KEY_DISPATCHING permission" in crash
    preview_error="PreviewManagerImpl.changePreviewSurfaceSize" in crash and "NullPointerException" in crash
    has_preview=bool(re.search(r"0x[0-9a-f]{8}\s*\(availablePreviewStreamConfigurations\).*samsung.android.scaler",service,re.I))
    has_picture=bool(re.search(r"0x[0-9a-f]{8}\s*\(availablePictureStreamConfigurations\).*samsung.android.scaler",service,re.I))
    info=[
        "ALICE A16 Samsung Camera POST-FLASH report (not a repair)",
        "camera_running_after_8s="+str(bool(re.fullmatch(r"\d+(\s+\d+)*",pid))).lower(),
        "actual_radio_default="+version.strip(),
        "vendor_preview_tag_registered="+str(has_preview).lower(),
        "vendor_picture_tag_registered="+str(has_picture).lower(),
        "camera_APP_JAVA_crash_found="+str(bool(crash)).lower(),
        "system_key_permission_crash="+str(permission_error).lower(),
        "preview_null_exception="+str(preview_error).lower(),
        "vendor_camera_bridge_file_present="+str("camera.alice-hlong.universal8895.so" in bridge).lower(),
        "NOTE: tag registration alone does not confirm metadata per camera or working video.",
        "Only Samsung Camera was force-stopped and relaunched. No flash, permission or SIM changes.",
    ]
    (d/"summary.txt").write_text("\n".join(info)+"\n")
    print("\n".join(info))
    print("REPORT:",d/"summary.txt")
    if crash:print("\nLATEST APP EXCEPTION (inspect for private data):\n",crash[:2700])
    print("PRIVATE raw logs stay on laptop; review filtered file before sharing.")
if __name__=="__main__":run()
