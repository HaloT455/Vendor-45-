#!/usr/bin/env bash
# ALICE S8+ Samsung Camera acceptance test. READ-ONLY apart from launching Camera,
# resetting logcat buffer, and writing logs on the host. No vendor/kernel flash.
set -euo pipefail
OUT="${1:-ALICE_CAMERA_TEST_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
adb wait-for-device
adb shell getprop ro.product.device > "$OUT/device.txt"
adb shell getprop ro.build.version.sdk >> "$OUT/device.txt"
adb shell su -c 'dumpsys media.camera' > "$OUT/camera_before.txt" 2>&1 || true
adb shell dumpsys package com.sec.android.app.camera > "$OUT/package.txt" 2>&1 || true
adb shell dumpsys package permissions > "$OUT/permissions.txt" 2>&1 || true
adb logcat -c
adb shell monkey -p com.sec.android.app.camera -c android.intent.category.LAUNCHER 1 > "$OUT/launch.txt" 2>&1 || true
echo "Wait 12 seconds. Do not interact with the phone."
sleep 12
adb logcat -d -v threadtime > "$OUT/logcat.txt"
adb shell su -c 'dumpsys media.camera' > "$OUT/camera_after.txt" 2>&1 || true
adb shell dumpsys activity exit-info com.sec.android.app.camera > "$OUT/exits.txt" 2>&1 || true
python3 - "$OUT" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
log=(p/'logcat.txt').read_text(errors='replace')
pkg=(p/'package.txt').read_text(errors='replace')
cam=(p/'camera_after.txt').read_text(errors='replace')
key='Requires ACCESS_SYSTEM_KEY_DISPATCHING permission'
checks={
  'framework_permission_crash':key in log,
  'preview_completed':'onStartPreviewCompleted' in log,
  'missing_preview_tag':'availablePreviewStreamConfigurations' in log and 'not supported' in log,
  'missing_picture_tag':'availablePictureStreamConfigurations' in log and 'not supported' in log,
  'privileged_system_app':'PRIVATE_FLAG_PRIVILEGED' in pkg or ' PRIVILEGED ' in pkg,
  'camera_service_reports_streams':'Stream' in cam and 'Output' in cam,
}
with (p/'result.txt').open('w') as f:
  for name,value in checks.items():
    f.write(f'{name}={value}\n')
  if checks['framework_permission_crash']:
    f.write('NEXT=FRAMEWORK_OR_APP_PERMISSION; do not change Camera HAL for this exception\n')
  else:
    f.write('NEXT=REVIEW_LOGCAT; no success assumed without visible preview and saved photo\n')
print((p/'result.txt').read_text())
PY
echo "Logs saved in $OUT"
