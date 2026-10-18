# ALICE S8+ Android 16 — DSDS per-SIM network default vendor trial

**Experimental vendor image. NOT FLASH READY.**

## Observed evidence

2026-10-19 logs from Exynos8895 Android 16:
- SIM1 / PhoneId0: CS DENIED on UMTS, PS NOT_REG_OR_SEARCHING, OUT_OF_SERVICE.
- SIM2 MobiFone / PhoneId1: CS HOME on UMTS, PS HOME on HSUPA, IN_SERVICE.
- LTE and LTE_CA appear in both allowed bitmasks, neither SIM has proven real LTE registration.
- Both mUserMobileDataState=false in the capture. This cannot explain SIM1 CS registration DENIED.

## Exact vendor changes

1. `vendor/build.prop` now declares `ro.telephony.default_network=9,9` (an Android sysprop IntegerList) instead of relying on a single default value `9`. Each value 9 means GSM/WCDMA/LTE auto, **not LTE-only**, and does not imply both SIMs can register LTE concurrently.
2. `vendor/etc/init/init.vendor.rilcommon.rc` no longer tries to set the read-only `ro.telephony.default_network` property late, during `post-fs-data`, using a single-SIM integer. The original Samsung `network_config` remains.
3. Tests verify the two existing HIDL slot instances and the original Android 13 VNDK33 HAL contract. No CP/IMEI/EFS change.

Supporting reference: AOSP TelephonyProperties.sysprop defines `ro.telephony.default_network` as `IntegerList`: https://android.googlesource.com/platform/system/libsysprop/+/refs/heads/master/srcs/android/sysprop/TelephonyProperties.sysprop
Samsung Exynos9810 Lineage device example: https://github.com/LineageOS/android_device_samsung_exynos9810-common/blob/lineage-20/vendor.prop

## RAF overlay finding: redundant experiment NOT included

The original `vendor/overlay/framework-res__auto_generated_rro_vendor.apk` **already contains** the resource name `config_radio_access_family` and the literal `GSM|CDMA|EVDO|WCDMA|LTE`. Adding another RRO claiming to restore this string would have no justified benefit, and might shadow existing modem configuration. Earlier staged RRO tooling remains archived under tools/ for research, but the active CI deliberately does not use or package it.

An earlier log recorded `GET_RADIO_CAPABILITY` invalid response and fake RAF=0. This is historical, not reproduced in the most recent log. If framework continues using RAF0 after confirming a compatible overlay and default network list, the remaining issue is probably at the radio HAL/framework callback or modem response, not a missing resource.

## What this cannot prove

- That the installed Android 16 system accepts the new vendor default ahead of its own `ro.telephony.default_network=9` property. The runtime value must be checked before claiming this change took effect.
- That SIM1 registration denied by the network is repaired.
- That SIM2 successfully registers LTE instead of HSUPA.
- That the modem supports simultaneous Dual 4G; Exynos8895 DSDS may allow only one LTE-capable stack.
- That the experimental EROFS image fits the actual physical vendor partition. The CI image has a research size ceiling larger than the original image. **Do not flash without checking partition geometry and a tested rollback path.**

## CI and rollback

Branch: `work/dual-sim-lte-raf-trial`. The original `baseline/test7` and the `work/android16-vendor-compat` branch remain unchanged. Workflow produces `vendor-dsds-default9x2-UNTESTED.img` and a verification report. The report is an offline structural result only.

Safe rollback is returning to the previously verified booting Test7 image through a proven recovery procedure. Never clear EFS/NV or experiment on modem calibration.
