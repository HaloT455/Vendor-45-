#!/usr/bin/env bash
# ALICE Android16 Exynos8895 READ-ONLY vendor-runtime diagnostics.
set -uo pipefail
export LC_ALL=C
command -v adb >/dev/null || { echo "adb missing" >&2; exit 2; }
adb -d get-state >/dev/null || { echo "Connect one S8+ via USB ADB" >&2; exit 2; }
OUT="$HOME/Downloads/ALICE_A16_VENDOR_RUNTIME_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "ALICE Android16 / Exynos8895 runtime inventory: $OUT"
run() {
  local name="$1"
  shift
  if ! timeout 30 adb -d "$@" > "$OUT/$name" 2>&1; then
    printf '[WARN] Failed or timed out: %s\n' "$name" >> "$OUT/$name"
  fi
}
{
  for key in ro.build.version.sdk ro.build.version.release ro.build.version.security_patch \
    ro.vendor.build.version.sdk ro.vendor.build.version.release \
    ro.vndk.version ro.product.vndk.version \
    ro.product.device ro.product.vendor.device \
    ro.board.first_api_level ro.product.first_api_level \
    ro.hardware.chipname ro.soc.model ro.boot.hardware \
    ro.boot.verifiedbootstate ro.control_privapp_permissions; do
    value="$(adb -d shell getprop "$key" 2>/dev/null | tr -d '\r')"
    printf '%s=%s\n' "$key" "$value"
  done
} > "$OUT/versions.txt"
run apex.txt shell 'ls -ld /apex/com.android.vndk* /apex/com.android.runtime /apex/com.android.media* 2>&1; cmd apex list 2>&1 | grep -Ei "vndk|runtime|media" | head -70'
run vintf_vendor_manifest.xml shell 'cat /vendor/etc/vintf/manifest.xml'
run vintf_vendor_matrix.xml shell 'cat /vendor/etc/vintf/compatibility_matrix.xml'
run vintf_framework_locations.txt shell 'ls -l /system/etc/vintf /system_ext/etc/vintf /product/etc/vintf /vendor/etc/vintf/manifest 2>&1'
run hal_services.txt shell 'service list 2>&1 | grep -Ei "camera|media|codec|face|biometric|audio|graphics|fingerprint|gatekeeper|radio|nfc"'
run hidl_services.txt shell 'lshal 2>&1 | grep -Ei "camera|face|codec|media|graphics|audio|radio|nfc|fingerprint|gatekeeper"'
run processes.txt shell 'ps -A 2>&1 | grep -Ei "cameraserver|camera.provider|face|biometric|mediacodec|media.codec|omx|mfc|codec2|c2@|rild|hwcomposer"'
run face_init.txt shell 'getprop init.svc.sec-biometrics-face-aidl; getprop init.svc.vendor.samsung.hardware.biometrics.face-service; ls -l /vendor/bin/hw/*face* /vendor/etc/init/*face* /vendor/etc/vintf/manifest/*face* 2>&1'
run camera_service.txt shell 'dumpsys media.camera'
run codec_service.txt shell 'dumpsys media.codec'
run devices.txt shell 'ls -l /dev/video* /dev/mfc* /dev/fimc* /dev/v4l* 2>&1'
run modules.txt shell 'ls -l /vendor/lib/vndk /vendor/lib64/vndk /system/lib64/vndk* 2>&1'
run linker_files.txt shell 'ls -l /linkerconfig/ld.config.txt /linkerconfig/ld.config.vndk_lite.txt /system/etc/ld.config* /vendor/etc/ld.config* 2>&1'
run selinux.txt shell 'getenforce; getprop ro.boot.selinux; getprop ro.vendor.build.security_patch'
# Only selected error lines; inspect before sharing as private context can remain.
if ! timeout 30 adb -d logcat -d -b all -v threadtime -t 16000 2>/dev/null |
  grep -Ei 'CANNOT LINK EXECUTABLE|dlopen failed|library .* not found|VNDK|VINTF|hwservicemanager|servicemanager|avc: denied|linkerconfig|cameraserver|ExynosCamera|CameraService|FaceService|biometric.*face|OMX.*(error|fail)|MediaCodec.*(error|fail)|codec2.*(error|fail)' |
  tail -n 1600 > "$OUT/platform_filtered.log"; then
  echo '[WARN] No matching logcat lines or logcat denied' >> "$OUT/platform_filtered.log"
fi
cat > "$OUT/README.txt" <<'EOF'
READ ONLY. No install, permission grants, kernel/vendor writes or reboot.
Review platform_filtered.log for personal information before sharing.
Android16 is API36, NOT a VNDK36 upgrade. A legacy VNDK33 vendor may still boot.
HAL service presence is not evidence of working camera/video/face functionality.
EOF
ARCHIVE="$OUT.tar.gz"
tar -czf "$ARCHIVE" -C "$OUT" .
echo "DONE: $ARCHIVE"
