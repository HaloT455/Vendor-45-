#!/usr/bin/env python3
"""ALICE S8+ Samsung Camera shutter-to-file test: deliberate one-shot KEYCODE_CAMERA.

Measures host elapsed time from dispatching keyevent 27 to the first NEW JPEG/HEIC
appearing in /sdcard/DCIM/Camera. It is NOT sensor exposure time; it includes app
command dispatch, processing, filesystem visibility and ADB polling overhead.
Only run with Samsung Camera OPEN in Photo mode, aimed at a non-private test scene.
The test TAKES and SAVES a photo; filenames and photo data are never printed.
Does not alter camera settings, clear logcat, or access biometric information.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time


DIRECTORY="/sdcard/DCIM/Camera"
EXTENSIONS=(".jpg",".jpeg",".heic")


def adb(*cmd:str,timeout:float=20)->str:
    p=subprocess.run(["adb","-d",*cmd],capture_output=True,text=True,
                     encoding="utf8",errors="replace",timeout=timeout)
    if p.returncode: raise RuntimeError(f"ADB command failed: {cmd[0]} (return {p.returncode})")
    return p.stdout


def photo_set()->set[str]:
    # Only names are read; no photos, file contents or location metadata.
    listed=adb("shell","ls","-1",DIRECTORY,timeout=15)
    return {name.strip() for name in listed.splitlines()
            if name.strip().lower().endswith(EXTENSIONS)}


def measure(timeout_sec:int,poll_sec:float)->dict:
    try: before=photo_set()
    except RuntimeError as e:
        raise RuntimeError("Cannot list /sdcard/DCIM/Camera; test cannot proceed") from e
    t0=time.monotonic()
    adb("shell","input","keyevent","27",timeout=12)
    dispatched=time.monotonic()-t0
    seen=False
    while time.monotonic()-t0<timeout_sec:
        time.sleep(poll_sec)
        after=photo_set()
        if after-before:
            seen=True
            break
    return {
        "new_photo_detected":seen,
        "shutter_command_to_new_file_seconds":round(time.monotonic()-t0,3) if seen else None,
        "adb_keyevent_return_seconds":round(dispatched,3),
        "time_limit_seconds":timeout_sec,
        "camera_keyevent_may_be_ignored":not seen,
        "photo_contents_read":False,
        "photo_name_printed":False,
        "latency_type":"host KEYCODE_CAMERA command -> new photo visible (NOT exposure time)"
    }


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--trials",type=int,default=3)
    a.add_argument("--max-wait",type=int,default=12)
    a.add_argument("--poll",type=float,default=0.35)
    a.add_argument("--output",type=str)
    a.add_argument("--selftest",action="store_true")
    z=a.parse_args()
    if z.selftest:
        x={"A.jpg","B.heic","C.png"}
        assert {q for q in x if q.lower().endswith(EXTENSIONS)}=={"A.jpg","B.heic"}
        print("PASS: filename type filter for privacy-safe shutter-to-file timer")
        return
    if not (1<=z.trials<=5 and 4<=z.max_wait<=30 and 0.1<=z.poll<=2):
        a.error("trials=1..5, max-wait=4..30, poll=0.1..2")
    print("OPEN Samsung Camera, Photo mode, fixed well-lit test scene.",flush=True)
    print("This will request and SAVE one test photo each trial; it will not read photos.",flush=True)
    try: input("When preview is READY, press Enter to start: ")
    except EOFError: a.error("Requires Terminal keyboard input")
    measures=[]
    for n in range(z.trials):
        print(f"TRIAL {n+1}/{z.trials}...",flush=True)
        try: result=measure(z.max_wait,z.poll)
        except (RuntimeError,subprocess.TimeoutExpired) as exc:
            a.exit(2,f"SHUTTER_PROBE_ERROR: {exc}\n")
        measures.append(result)
        print(json.dumps({"trial":n+1,**result},ensure_ascii=False),flush=True)
        if n+1<z.trials: time.sleep(1.0)
    v=[x["shutter_command_to_new_file_seconds"] for x in measures if x["new_photo_detected"]]
    summary={
        "median_keyevent_to_photo_file_seconds":round(statistics.median(v),3) if v else None,
        "successful_trials":len(v),
        "trials":measures,
        "warning":"Do not equate file-save duration with sensor shutter; KEYCODE_CAMERA may be ignored.",
    }
    if z.output:
        from pathlib import Path
        Path(z.output).expanduser().write_text(json.dumps(summary,indent=2)+"\n")
    print("SUMMARY",json.dumps(summary,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
