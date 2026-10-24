#!/usr/bin/env bash
# S8+ Android16 ALICE RAF0 preflight. Read-only USB adb; no su required.
# NO flash, push, remount, mount, setprop, shell scripts written to device.
set -euo pipefail

echo "===== ADB / S8+ DEVICE ====="
adb -d get-state
adb -d shell '
echo "===== DEVICE IDENTITY ====="
for p in ro.product.vendor.device ro.product.device ro.build.display.id ro.build.version.release ro.boot.verifiedbootstate; do
  echo "$p=$(getprop "$p")"
done
echo "===== KERNEL ====="
uname -r
echo "===== JAVA FRAMEWORK ====="
ls -l /system/framework/telephony-common.jar
sha256sum /system/framework/telephony-common.jar
echo "===== BOOTCLASSPATH TARGET ====="
printf "%s\n" "$BOOTCLASSPATH" | tr ":" "\n" | grep -F "/system/framework/telephony-common.jar" || true
echo "===== SELINUX ====="
getenforce 2>/dev/null || true
echo "===== RAF0 TRIAL PROPERTY (READ ONLY) ====="
echo "persist.vendor.alice.s8p_raf0_resource_fallback=$(getprop persist.vendor.alice.s8p_raf0_resource_fallback)"
echo "===== AVAILABLE VENDOR PROPERTY CONTEXTS ====="
for f in /vendor/etc/selinux/vendor_property_contexts /system/etc/selinux/plat_property_contexts /system_ext/etc/selinux/system_ext_property_contexts /product/etc/selinux/product_property_contexts /odm/etc/selinux/odm_property_contexts; do
    if [ -r "$f" ]; then
        grep -n -E "(^|[[:space:]])(persist\\.vendor\\.alice\\.|persist\\.vendor\\.)" "$f" | head -12 || true
    fi
done
echo "===== BOOTCLASSPATH ART COMPILE MODE ====="
getprop dalvik.vm.dex2oat-filter
getprop dalvik.vm.usejit
getprop ro.build.version.sdk
'
echo "===== HOST ORIGINAL FILE STILL MATCHES ====="
ORIGINAL="${HOME}/Downloads/ALICE_ROM_RADIO_DUMP/telephony-common.jar"
if [ -f "$ORIGINAL" ]; then
  echo "8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1  $ORIGINAL" | sha256sum -c -
else
  echo "Host original JAR missing (this does not affect phone): $ORIGINAL"
fi
echo "===== COMPLETE: READ ONLY, NO DEVICE CHANGES ====="
