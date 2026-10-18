#!/usr/bin/env bash
# ALICE Test7 S8+ : read-only camera video and face-unlock contract audit.
# Run on Zorin OS: bash tools/audit_camera_video_face_runtime.sh
set -euo pipefail
command -v adb >/dev/null
adb get-state | grep -qx device
DEST="${1:-$HOME/ALICE_CAMERA_LOG/audit_video_face}"
mkdir -p "$DEST"
adb shell dumpsys media.camera > "$DEST/media.camera.txt"
adb shell 'dumpsys biometric 2>&1' > "$DEST/biometric.txt" || true
adb shell 'dumpsys face 2>&1' > "$DEST/face.txt" || true
adb shell 'service list 2>&1' > "$DEST/services.txt"
adb shell 'getprop' > "$DEST/properties.txt"
adb shell 'su -c "ls -lZ /vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service /vendor/etc/init/face-default-sec.rc /vendor/etc/vintf/manifest/face-default-sec.xml /vendor/apex/com.samsung.android.biometrics.face.signed.apex 2>&1"' > "$DEST/face_vendor_files.txt" || true
adb shell 'su -c "getprop init.svc.sec-biometrics-face-aidl; pidof vendor.samsung.hardware.biometrics.face-service; ps -A -Z | grep -i face"' > "$DEST/face_service.txt" || true
adb shell 'su -c "ls /dev/block/by-name/ 2>/dev/null | head -5"' >/dev/null || true
adb logcat -d -b main,system,crash -v threadtime > "$DEST/logcat.txt"
{
  echo '===== Camera scaler vendor registration ====='
  grep -E 'available(PreviewStream|PictureStream|Video)Configurations|Dumping configured vendor tag descriptors' "$DEST/media.camera.txt" | tail -30 || true
  echo '===== Face service ====='
  cat "$DEST/face_service.txt"
  echo '===== Face API services ====='
  grep -i -E 'face|biometr' "$DEST/services.txt" | head -50 || true
  echo '===== Recent face errors ====='
  grep -i -E 'face.*(error|fail|denied|crash)|biometric.*(error|fail|denied)|android.hardware.biometrics.face|avc: denied' "$DEST/logcat.txt" | tail -100 || true
  echo '===== Samsung Camera video metadata errors ====='
  grep -i -E 'availableVideoConfigurations|firstRecorderSurfaceSize|checkAvailableDeviceConfiguration|ExynosCamera.*timeout' "$DEST/logcat.txt" | tail -50 || true
} | tee "$DEST/summary.txt"
echo "Reports: $DEST"
echo "READ-ONLY; DOES NOT FIX OR FLASH ANYTHING"
