#!/usr/bin/env bash
# ALICE / S8+ Exynos8895 / Android 16 -- dual-SIM LTE RIL diagnostics.
# Read-only. Never reads modem NV/EFS or changes CP / network settings.
set -euo pipefail
command -v adb >/dev/null
adb -d get-state | grep -qx device
out="${1:-$HOME/Downloads/ALICE_SIM_LTE_A16_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$out"
capture() { local target="$1"; shift; if ! timeout 35 adb -d "$@" > "$out/$target" 2>&1; then echo '[WARN] failed/timed out' >> "$out/$target"; fi; }
capture slot0_allowed.txt shell cmd phone get-allowed-network-types-for-users -s 0
capture slot1_allowed.txt shell cmd phone get-allowed-network-types-for-users -s 1
capture phone.txt shell dumpsys phone
capture telephony_registry.txt shell dumpsys telephony.registry
capture isub.txt shell dumpsys isub
capture carrier_config.txt shell dumpsys carrier_config
capture radio_services.txt shell 'lshal 2>&1 | grep -i -E "radio|ril|sehradio"'
capture versions.txt shell 'for k in ro.build.version.sdk ro.vendor.build.version.sdk ro.vndk.version ro.vendor.sec.radio.def_network ro.telephony.default_network persist.radio.multisim.config ro.vendor.multisim.simslotcount; do printf "%s=" "$k"; getprop "$k"; done'
timeout 35 adb -d logcat -b radio -d -t 16000 -v threadtime 2>/dev/null |
  grep -iE 'RILJ|RADIO_CAPABILITY|RadioCapability|RAF|ServiceState|LTE|IMS|setPreferredNetwork|setAllowedNetwork|getDataRegistrationState|REQUEST_NOT_SUPPORTED|RADIO_NOT_AVAILABLE|OUT_OF_SERVICE|slot[012]' |
  tail -n 1200 > "$out/radio_filtered.log" || true
timeout 35 adb -d logcat -b main,system -d -t 16000 -v threadtime 2>/dev/null |
  grep -iE 'RadioCapability|RIL_REQUEST_GET_RADIO_CAPABILITY|LTE is configured on other stack|PhoneSwitcher|RadioConfig' |
  tail -n 350 > "$out/framework_radio.log" || true
cat > "$out/README.txt" <<'EOF'
ALICE Exynos8895 / Android16 radio diagnosis. Read-only, no modem changes.
Slot 0 = SIM1. Slot 1 = SIM2. Select each as Mobile data SIM before a separate capture.
IMPORTANT: service dumps and radio logs can include ICCID/IMEI/IMSI/cell location.
Review and redact all files prior to sharing.
Existing Android16 runtime and Face AIDL diagnostic archives DO NOT include these logs.
A slot having an LTE-capable bitmask is not proof that LTE is registered.
EOF
echo "Collected: $out"
grep -ihE 'Invalid response|Faking RIL_REQUEST_GET_RADIO_CAPABILITY|LTE is configured on other stack|REQUEST_NOT_SUPPORTED|RADIO_NOT_AVAILABLE' "$out"/*.log | tail -n 30 || true
