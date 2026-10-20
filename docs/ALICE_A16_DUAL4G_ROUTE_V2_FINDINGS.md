# ALICE S8+ A16 — why snapshots can be misleading

Reports captured on 2026-10-20 09:58:28 and 10:01:55 showed mobileDataUser=true on both phone IDs but **exactly the same WWAN result**: SIM1 CS DENIED/PS NOT_REG_OR_SEARCHING on UMTS, SIM2 CS HOME/PS HOME on HSUPA. There was no LTE registration and no recorded RAF0 or CP second-LTE rejection. The user-enabled data setting being true for both does **not** establish which SIM is the actual default data subscription, nor does a report label (`--snapshot sim1`) switch it.

To discriminate without touching CP/EFS or camera firmware, run locally:
```
adb -d shell 'dumpsys isub | grep -iE "defaultDataPhoneId|defaultDataSubId" | head'
```
`defaultDataPhoneId=0` should correspond to physical SIM1 and `defaultDataPhoneId=1` to SIM2, provided both are active. If only `defaultDataSubId` is printed, map that to the active SIM-slot index, without sharing ICCIDs.

Use the local sanitized tool `ALICE_A16_DUAL4G_ROUTE_V2.py` (selftest, report) to verify routing after manually selecting SIM1 and SIM2, then recheck WWAN registration. If the default route genuinely changes but SIM1 still DENIED and SIM2 stays HSUPA, the next differential test is a **single-SIM-only carrier/slot test** or a controlled radio-command trace. No evidence currently warrants writing a replacement vendor image.

This branch inherits the confirmed working Samsung Camera Video6. Never modify the existing camera HAL on this radio investigation.

## Runtime property discrepancy — verify before building a new radio vendor image

Both user dumps report `ro.vendor.sec.radio.def_network=(empty)` on device, whereas this branch's source `vendor/build.prop` includes `ro.vendor.sec.radio.def_network=9`. It is **not yet proven** this mismatch causes the lack of LTE; however, the actual flashed image and property-load order should be checked without flashing anything:

```sh
adb -d shell 'echo ACTUAL_RUNTIME; getprop ro.vendor.sec.radio.def_network; getprop ro.telephony.default_network; echo CONTENTS_VENDOR_BUILD_PROP; grep -E "^(ro.vendor.sec.radio.def_network|ro.telephony.default_network)=" /vendor/build.prop; echo DEFAULT_DATA; dumpsys isub | grep -iE "defaultDataPhoneId|defaultDataSubId" | head -8'
```

A source-file property does not necessarily appear in Android's runtime if an older image was flashed, init did not load it, or another property source superseded it. Do not try to modify `ro.` properties live or claim cause without evidence.
