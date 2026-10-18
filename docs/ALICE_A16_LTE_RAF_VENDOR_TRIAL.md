# ALICE S8+ / Android 16: standalone RAF fallback trial

**Status: experimental, NOT FLASH READY. Do not flash the generated image.**

## Evidence

The 2026-10-19 runtime capture shows SIM1 PhoneId0 registration CS=DENIED / PS=NOT_REG_OR_SEARCHING on UMTS, SIM2 MobiFone PhoneId1 CS=HOME on UMTS and PS=HOME on HSUPA. Both user allowed network masks contain LTE, but this does not prove LTE attachment. User mobile data was disabled at the time of capture. Previous traces (not the latest) showed invalid RadioCapability responses and RIL fake RAF=0.

## Vendor change

This branch adds a narrowly-scoped *static Radio Access Family fallback* resource overlay containing `config_radio_access_family = GSM|WCDMA|LTE`. AOSP documents this value as a fallback **only for a RIL that does not support GET_RADIO_CAPABILITY**, not as a way to add LTE bands or physically upgrade the modem. This can potentially stop Android Telephony treating unknown radio capability as RAF 0.

The signed RRO is integrated via `tools/integrate_radio_raf_standalone.py` into the vendor EROFS tree in CI. The integration changes only the experimental checkout's vendor overlay and EROFS metadata; no original vendor blobs are recompiled or changed.

Official AOSP reference: https://android.googlesource.com/platform/frameworks/base/+/android16-qpr1-release/core/res/res/values/config.xml
Static RAF legacy framework logic: https://android.googlesource.com/platform/frameworks/opt/telephony/+/3ad0c75%5E%21/

## Limitations / gates

1. The exact installed One UI 8 Android16 framework and overlayable policy are not fully verified. The RRO may be rejected by idmap or overridden by a higher-priority overlay. Verify using `cmd overlay list --user 0 android` and the Android framework's effective resource, without publishing personal data.
2. AOSP RIL fallback only applies to certain error responses. If the modem returns an invalid success payload instead, this may require a **system/framework-side** compatibility change rather than a vendor RRO.
3. SIM1 CS=DENIED remains unexplained by RAF=0 alone; independently check card in both slots, carrier provisioning, and explicit modem registration errors.
4. The Galaxy S8+ Exynos8895 CP may limit LTE registration to one stack. **This trial does not promise Dual LTE simultaneous**.
5. CI builds an EROFS research image with up to 16 MiB extra headroom. This is a build ceiling, **not** an assertion that the physical vendor partition has this capacity. The image must not be flashed before exact target partition geometry, rollback and live idmap are verified.
6. Preserve IMEI/EFS, CP, modem NV, baseband and kernel. No ADB property forcing of LTE-only or false bands.
7. New experimental branch only. `baseline/test7` and `work/android16-vendor-compat` remain intact.

## CI

Open the workflow `ALICE S8Plus Android16 radio RAF vendor trial (NOT FLASH READY)` on branch `work/dual-sim-lte-raf-trial`. It builds and signs a separate RRO APK, stages EROFS metadata, runs offline checks and attempts to produce `vendor-radio-raf-UNTESTED.img`. Passing CI does not prove radio functionality.

## Rollback

Do not install until full target verification. A rollback plan requires retaining the known-booting Test7 `vendor.img`, ensuring recovery/TWRP access and validating checksums before any flash. To revert the repository experiment, leave this branch and use `work/android16-vendor-compat`. No changes to IMEI/EFS are permitted.
