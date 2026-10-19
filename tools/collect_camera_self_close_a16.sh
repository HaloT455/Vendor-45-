#!/usr/bin/env bash
# ALICE S8+ Android16 Samsung Camera self-close triage; no flash/permission grants.
set -euo pipefail
command -v adb >/dev/null
adb -d get-state | grep -qx device
OUT="${1:-$HOME/Downloads/ALICE_CAMERA_CLOSE_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
PKG=com.sec.android.app.camera
capture() {
  local filename="$1"; shift
  timeout 35 adb -d "$@" > "$OUT/$filename" 2>&1 || echo "[WARN] command timed out/failed" >> "$OUT/$filename"
}
capture app_package.txt shell dumpsys package "$PKG"
capture app_path.txt shell pm path "$PKG"
capture permission.txt shell 'dumpsys package permissions | grep -F -A 12 "com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING" | head -30'
capture init_camera.txt shell 'getprop ro.build.version.sdk; getprop ro.product.vendor.device; dumpsys media.camera | grep -E "availablePreviewStreamConfigurations|availablePictureStreamConfigurations" | head -20'
capture modules.txt shell 'su -c "ls -ld /data/adb/modules/alice_samsung_camera_privapp /data/adb/modules/alice_samsung_camera_privapp/system/priv-app/ALICE_SamsungCamera 2>&1"'
adb -d shell am force-stop "$PKG" >/dev/null 2>&1 || true
capture launched.txt shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1
sleep 7
capture camera_pid.txt shell pidof "$PKG"
capture exit_info.txt shell dumpsys activity exit-info "$PKG"
capture log_private.txt logcat -d -b main,system,crash -v threadtime -t 14000
python3 - "$OUT" <<'PY'
import re,sys
from pathlib import Path
p=Path(sys.argv[1])
s=(p/"log_private.txt").read_text(errors="replace")
keys=("FATAL EXCEPTION","ACCESS_SYSTEM_KEY_DISPATCHING","SecurityException",
      "PreviewManagerImpl","availablePictureStreamConfigurations",
      "availablePreviewStreamConfigurations","Fatal signal","UnsatisfiedLinkError",
      "CameraWindowManager","NoSuchMethodError","CameraService","camera.provider")
lines=s.splitlines(); at=set()
for i,x in enumerate(lines):
 if any(k.casefold() in x.casefold() for k in keys):
  at.update(range(max(0,i-2),min(len(lines),i+9)))
safe="\n".join(f"{i+1}: {lines[i]}" for i in sorted(at)[-220:])
(p/"camera_crash_filtered.txt").write_text(safe+"\n")
permission="Requires ACCESS_SYSTEM_KEY_DISPATCHING permission" in s
print("system_key_permission_crash=",permission)
print("camera_pid_after_7s=",(p/"camera_pid.txt").read_text(errors="replace").strip())
print("logs_folder=",p)
print("SHARE ONLY AFTER REDACTING identifiers; use camera_crash_filtered.txt")
print("\n".join(safe.splitlines()[-80:]))
PY
