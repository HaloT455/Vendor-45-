# ALICE S8+ Android 16 — Dual SIM LTE runtime repair investigation (2026-10-20)

## Baseline preserved
Branch forked from `work/a16-camera-video6-metadata-fix` AFTER the user confirmed Samsung Camera + video working and restored with `pm clear com.sec.android.app.camera`. Do not modify or revert camera bridge, video metadata, original Exynos camera delegates or runtime camera system permissions. This branch is **diagnostic-only until mobile-network evidence establishes a reproducible radio bug**.

## Prior radio evidence (2026-10-19)
- PhoneId0 SIM1: voice CS DENIED UMTS, PS not registered/searching UMTS, OUT_OF_SERVICE.
- PhoneId1 SIM2: voice CS HOME UMTS, PS HOME HSUPA, IN_SERVICE, no proven LTE attach.
- Both masks permitted LTE/LTE_CA; `persist.radio.multisim.config=dsds`; `ro.vendor.multisim.simslotcount=2`.
- On previous runtime, user mobile data was OFF on both slots. That prevents user data use but does not explain SIM1's voice network rejection.
- In the earlier static CP firmware strings: `LTE is configured on other stack`; *not* a recent contemporaneous LTE handoff log. Historical `RIL_REQUEST_GET_RADIO_CAPABILITY` RAF0/invalid capability logs must also be rechecked before patching.
- Current vendor configuration already includes `ro.telephony.default_network=9,9`, two HIDL 1.6 IRadio instances, 2 vendor Samsung radio HAL instances. Configuration alone does NOT prove two simultaneous LTE registrations.

## Next read-only, controlled comparison
1. Record BOTH inserted state (no changes).
2. Manually designate SIM1 as default MOBILE DATA SIM in Android settings; enable mobile data and LTE/3G/2G auto. Wait for cellular registration; record SIM1 snapshot.
3. Manually designate SIM2 as default MOBILE DATA SIM, same network mode, record SIM2 snapshot.
4. For each snapshot, extract separate PhoneId0/1 WWAN CS and PS registration, data RAT, voice RAT, user data enabled, runtime 9,9, sysfs DS detect, radio capability fallback and modem second stack denial; distinguish allowed masks from actual 4G attach.
5. If both individual slots use LTE but not concurrently, determine if modem LTE owner handoff occurs; simultaneous LTE may be limited by Exynos8895 CP RF scheduling. Do not flash a fake 'dual 4G' vendor based only on permissions.
6. If SIM1 still CS DENIED when it alone is designated default data, test that same physical SIM in the other slot or known good handset before changing radio firmware; network rejection may follow the SIM/carrier.
7. A dedicated local read-only anonymized snapshot tool has a selftest and reports PhoneId WWAN states. Never upload raw radio logcat/dumpsys with subscriber IDs.

## Constraints
No new vendor image is warranted from historical 9,9/default mask evidence; no modifications to modem CP, EFS, IMEI, NV, band calibration, serial identifiers or flashing. Keep last known functional Camera+Video6 firmware backed up. If an active framework/HAL error is isolated, fix only radio files and verify camera content byte-for-byte unchanged.

## 2026-10-20 user two-switch snapshot assessment

User provided two post-CameraVideo6 reports 10 seconds apart, at 09:48:50 (`snapshot=sim1`) and 09:49:00 (`snapshot=sim2`). These are **manual labels only** passed through `--snapshot`; the script does NOT select a default mobile-data SIM, enable data, or trigger LTE switching. Both reports show exactly:
- PhoneId0: CS DENIED UMTS, PS NOT_REG_OR_SEARCHING UMTS, voice/data OUT_OF_SERVICE, `mUserMobileDataState=false`.
- PhoneId1: CS HOME UMTS, PS HOME HSUPA, voice/data IN_SERVICE, `mUserMobileDataState=false`.
- `ro.telephony.default_network=9,9`, `persist.radio.multisim.config=dsds`, `ds_detect=2`, two SIMs LOADED.
- Historical error counters are zero for CP second-LTE refusal, RAF0, invalid RadioCapability, RADIO_NOT_AVAILABLE; these do **not** prove Radio HAL health because no explicit network type attempt occurred.

**Gate:** Distinguish *actual default data selection and user data enabled setting* via `dumpsys isub` (`defaultDataPhoneId`, `defaultDataSubId`) and `dumpsys telephony.registry` before any vendor change. AOSP maps `svc data enable` to `cmd phone data enable`, which can be exercised on the currently selected default mobile-data subscription if the user elects. Once data is enabled, capture data-enabled + 30s attach and network transition for SIM1 and SIM2 separately. Do not alter LTE masks or CP/EFS to compensate for data disabled. SIM1's CS DENIED requires independent investigation if it persists after single-SIM checks.

No new radio vendor artifact should be advertised as fixing two LTE registrations based solely on the three identical captures.

## 2026-10-20 10:19:25, V3 actual routing result

New read-only V3 snapshot ("both") successfully mapped subscription to **default MOBILE DATA SIM2**, with two SIM-slot subscription records. `mUserMobileDataState=true` for both; SIM1 PS NOT_REG_OR_SEARCHING and CS DENIED UMTS, SIM2 PS HOME HSUPA and CS HOME UMTS. No LTE attach. This proves that SIM2 remains on 3G when selected as the actual default mobile-data route. The UI report does NOT establish that SIM1 was ever selected as the actual default: do not mistake V2 manual `sim1` labels for evidence.

A controlled single-SIM test should distinguish simultaneous-stack restrictions from each card's individual LTE ability. A contemporaneous Samsung Members technical support response dated March 2018 indicated an S8-class Samsung device allows only one SIM to use LTE at a time, with the other SIM moved to a lower mode: https://r2.community.samsung.com/t5/Galaxy-S/How-can-i-get-those-sim-4G-network/m-p/160770 . This is evidence against promising simultaneous dual LTE from a vendor property alone, but not a substitute for testing Exynos8895/CP on this specific handset.

Current next test with minimal churn: disable SIM1 in Settings (DO NOT remove/flash) while SIM2 remains selected as default-data, observe whether SIM2 moves to LTE on its own and whether RIL tries to set network type. Capture same V3 both snapshot after 30-60 s. Then restore both SIMs; if SIM2 can reach LTE alone, investigate CP LTE role hand-off. If SIM2 cannot reach LTE alone, investigate SIM2/carrier LTE provisioning/network mode and Radio HAL registration. SIM1 should later be checked alone and card-swap tested due to CS DENIED. Do not patch modem CP/NV or fake dual 4G reports.

## 2026-10-20 10:23:04 follow-up after requested SIM1-off test

The V3 snapshot is BYTE-FOR-BYTE equivalent in the radio states of both physical slots to the 10:19 snapshot:
- SIM1 PhoneId0 CS DENIED (UMTS), PS NOT_REG_OR_SEARCHING, voice/data OUT_OF_SERVICE, userData=true
- SIM2 PhoneId1 CS HOME (UMTS), PS HOME (HSUPA), userData=true; REAL default-data SIM is SIM2
- Both physical SIM states remain LOADED, `ds_detect=2`, two slot-map records, `ro.telephony.default_network=9,9`
- No contemporaneous RAF=0 / invalid RadioCapability / LTE-other-stack response captured; no observed set-network-type attempt

**Do not infer single-SIM LTE failure from this snapshot.** It does NOT demonstrate that SIM1 became radio POWER_OFF; `LOADED` alone also cannot prove SIM1 remained powered. Must validate with SIM1 telephony ServiceState POWER_OFF or explicit state in the SIM Manager (or safely remove SIM1 with the handset powered down), then repeat LTE attach for SIM2 in genuinely single-SIM configuration. If it still attaches only UMTS/HSUPA, investigate carrier/network LTE support and live radio network-selection/RIL events before patching vendor. No camera/CP/EFS changes authorized.

## 2026-10-20 11:23:55 — latest V3 report
- SIM1 PhoneId0: CS DENIED UMTS, PS NOT_REG_OR_SEARCHING UMTS; service OUT_OF_SERVICE; user data enabled.
- SIM2 PhoneId1: CS HOME UMTS, PS HOME HSPA+; service IN_SERVICE; selected DEFAULT MOBILE DATA, user data enabled.
- HSPA+ is still 3G, not LTE. A transition HSUPA -> HSPA+ does not satisfy LTE test.
- `gsm.sim.state=LOADED,LOADED`; two subscription records; `ds_detect=2`. These **do not establish successful SIM1 power-off or physical removal**. In a verified powered-down, physically removed SIM1 test after fresh boot, expect Android Telephony SIM state ABSENT for that slot (pending OEM quirks); if still LOADED, investigate SIM mapping/state handling before CP modifications.
- `ro.telephony.default_network=9,9`, no new RadioCapability/RAF0/CP second-stack reject in filtered period and 0 set network mode attempts observed.
- Preserve good Camera Video6 vendor. No LTE fix exists yet. Next evidence is confirmed SIM1 card-absent state + SIM2 WWAN RAT or carrier network mode check.

## 2026-10-20 11:22 subsequent confirmed preferred mode + baseband

On live S8+ Exynos8895 Android 16:
- `settings get global preferred_network_mode` = `9,9`; per-slot suffixed keys 0,1,2 return `null` (not proof of failure; base setting holds a comma-separated list).
- `getprop ro.telephony.default_network` = `9,9`; DSDS set; `getprop gsm.version.baseband` = `G955FXXUCDUD1,G955FXXUCDUD1` (April 2021-era CP revision).
- Repository vendor image `vendor/build.prop` references `G955FXXUCDVI2` (2022 firmware Android9 vendor; *does not prove* live modem/RIL ABI incompatibility). On previous captured runtime `ro.vendor.sec.radio.def_network` reported empty despite source declaring 9: check actual /vendor/build.prop and init/property ownership rather than treating as demonstrated LTE failure.
- Public AOSP `RILConstants.NETWORK_MODE_LTE_GSM_WCDMA=9` (https://android.googlesource.com/platform/prebuilts/fullsdk/sources/+/88c7ff1cd72d6305ec59f97aadc2198cc2dc3592/android-34/com/android/internal/telephony/RILConstants.java), so the existing preferred_network_mode does NOT disable LTE.
- SM-G955F hardware supports LTE B3 / 1800 MHz used by MobiFone (see https://www.frequencycheck.com/carrier-compatibility/oJWXCL/samsung-sm-g955f-galaxy-s8-plus-td-lte-samsung-dream-2/mobifone-vietnam). This does not guarantee LTE coverage or provisioning for the physical SIM.
- No validated reason yet for SIM1 CS DENIED, SIM2 HSPA+. **Do not patch 9,9 or flash newer CP merely because build labels differ.** Preserve stable camera/video vendor; best high-signal next test is manually ask Samsung UI to scan available operators on SIM2 LTE/3G/2G automatic, combined with one-SIM-only hardware test if safe: observe if LTE 4G network is *discoverable* and whether LTE registration succeeds. If 4G shown but no attach, debug subscription/CP/RIL registration; if scan never returns 4G while other known-good devices do at same site, debug CP/RIL RF/LTE enablement. Verify SIM1 radio truly powered down/removal separately.

## 2026-10-20 targeted new lead: Samsung EFS telephony.prop policy override

Exact AOSP/Lineage Samsung configuration service source:
https://github.com/LineageOS/android_hardware_samsung/blob/lineage-24.0/ril/secril_config_svc/secril_config_svc.cpp

`secril_config_svc NetworkConfig` reads `/mnt/vendor/efs/telephony.prop` (falling back to `/efs/telephony.prop`), extracts `persist.radio.def_network`, then publishes `persist.radio.def_network` and `ro.vendor.radio.default_network`. Our S8+ vendor uses the same `/vendor/bin/secril_config_svc NetworkConfig` as the `network_config` one-shot started on post-fs-data. This creates a **second network policy configuration path** distinct from `settings global preferred_network_mode=9,9` and `ro.telephony.default_network=9,9`.

**Do not assume** 9,9 proves the vendor/CP path permits LTE until `persist.radio.def_network` and `ro.vendor.radio.default_network` are checked on the device. In particular, if the persisted value is legacy `3` or `3,3`, it is a plausible cause of 3G selection even though user settings allow LTE. This is not yet observed on the device and must not be called a completed repair. Stock Samsung dumps show `ro.vendor.radio.default_network=9`, `ro.vendor.sec.radio.def_network=9` under ordinary GSM/WCDMA/LTE firmware; default network 9 must not be confused with a simultaneous DSDS two-LTE radio guarantee.

A local read-only, sanitized one-command tool `ALICE_A16_LTE_RIL_POLICY_AUDIT.py` has been created for the user to inspect the live property chain, file-vs-runtime mismatch, and service lifecycle without changing CP, EFS or the working Camera+Video6 vendor. If properties already enable LTE, **do not add an arbitrary property or build a speculative firmware image**: investigate modem registration and live scanning / service response, and confirm the SIM's 4G provisioning.

Separate hardware limitation: SM-G955FD DSDS evidence indicates at most one LTE registration at a time, the other SIM 3G; hardware CP capability cannot be forced by setting both mask bits.

## 2026-10-20 11:58:58 — RIL policy V2 result; next high-signal LTE policy intersection

New user V2 audit shows:
- `ro.telephony.default_network=9,9`, `ro.vendor.radio.default_network=9` both LTE-capable.
- `persist.radio.def_network` and `ro.vendor.sec.radio.def_network` blank (not proof of LTE blockage).
- `persist.radio.multisim.config=dsds`, slotcount=2, both SIMs LOADED, CP boot and RIL running.
- `init.svc.network_config=stopped`, `init.svc.sim_config=stopped` consistent with `oneshot` service lifecycle; no evidence that this is a fault.
- SIM1 CS DENIED / PS NOT_REG_OR_SEARCHING on UMTS. SIM2 HOME UMTS / PS HOME HSPA+. No LTE attach.
- Shell `/vendor/build.prop` not readable; this is a diagnostics access limitation, not itself a proven reason LTE fails.

**New priority informed by AOSP source**: `Phone.getEffectiveAllowedNetworkTypes()` ANDs all the allowed-network-type policies from `mAllowedNetworkTypesForReasons`, and `Phone.updateAllowedNetworkTypes()` ANDs the resulting effective mask with the modem's RAF. Hence `cmd phone get-allowed-network-types-for-users -s 1` only checks `USER`; `CARRIER`, `POWER`, `TEST`, `ENABLE_2G` can still remove LTE. Reference: https://github.com/LineageOS/android_frameworks_opt_telephony/blob/lineage-23.2/src/java/com/android/internal/telephony/Phone.java (API branch may differ; inspect code version when patching). The stored per-subscription reasons are available in `dumpsys isub` `SubscriptionInfoInternal.allowedNetworkTypesForReasons` as `user=<decimal>,power=<decimal>,carrier=<decimal>...` (never share its raw dump: contains SIM phone number/ICCID/IMSI). LTE bit: `4096` = `1 << 12`.

Created externally, offline-tested `ALICE_A16_LTE_EFFECTIVE_POLICY.py` to sanitize/inspect both slots' policy reasons and report `LTE_EXCLUDED_BY_<REASON>` when appropriate. If all stored reasons contain LTE, next study `modemRaf`, RIL network-scan and LTE network registration—not property tweaks or a speculative vendor flash. Preserve camera+video6 branch and CP/EFS/NV partitions.

## 2026-10-20 12:02:30 — Effective LTE policy report inconclusive; live RAF log trace next

Uploaded file `ALICE_A16_LTE_EFFECTIVE_POLICY_20261020_120230.txt`:
- SIM1: `UNKNOWN_NO_PER_REASON_POLICY` (no per-reason policy masks in output).
- SIM2: `UNKNOWN_NO_PER_REASON_POLICY` (no per-reason policy masks in output).
- `ro.telephony.default_network=9,9`, `ro.vendor.radio.default_network=9`, DSDS; `gsm.network.type=UMTS,IWLAN`, both SIMs LOADED.
- **Do not interpret absence of `allowedNetworkTypesForReasons` in `dumpsys isub` as LTE allowed or denied**. The previous tool cannot discriminate further on this ROM.

Framework logic verified from LineageOS `android_frameworks_opt_telephony` `Phone.java`:
`getEffectiveAllowedNetworkTypes` intersects `mAllowedNetworkTypesForReasons` and `updateAllowedNetworkTypes` intersects that with `getRadioAccessFamily()` before `mCi.setAllowedNetworkTypesBitmap(filteredRaf)`. `RIL.java` routes newer HIDL 1.6 through `RIL_REQUEST_SET_ALLOWED_NETWORK_TYPES_BITMAP`; on older HAL it falls back to `setPreferredNetworkType`. Thus live `Phone` debug messages (`modemRafBitMask`, `filteredRafBitMask`) are an informative next test, but may be missing from retained logs: *absence cannot be treated as modemRaf=0*.

A self-tested read-only Zorin Python utility `ALICE_A16_LTE_RAF_TRACE_V1.py` produces a privacy-filtered report from in-memory `dumpsys phone`, `dumpsys isub`, and `logcat -b radio`: numeric modem/filtered RAF and LTE bit `1<<12`, per-reason masks if present, radio error counts. No raw logs saved, no modem or vendor changes. Preserve working Video6 camera branch. **There is not yet a verified LTE fix or flash-ready vendor image**.

## 2026-10-20 12:06:06 — RAF V1 explicit abort, parser double-count corrected

User report `ALICE_A16_LTE_RAF_TRACE_20261020_120606.txt`:
- `unknown_raf_abort=8` is **8 matches for exact Android diagnostic `setPreferredNetworkType: Abort, unknown RAF`**. This is strong evidence that **some network-mode changes were aborted because the framework had no valid modem Radio Access Family (RAF) at those times**, not proof that it persists now or that SIM2 in particular generated all events. Unlike prior reports with zeros, investigate RadioCapability initialization and radio HAL forwarding.
- **V1 script double-counted:** `set_allowed_network_types=8` uses a regex that also matches `setPreferredNetworkType` appearing **inside those eight abort lines**. Therefore V1 does *NOT* prove 8 successful network-mode write requests! Corrected in privacy-safe V2 script.
- `ril_network_error=10` includes broad `REQUEST_NOT_SUPPORTED` (often `GET_BARRING_INFO`) and doesn't by itself diagnose LTE failure.
- `radio_capability_invalid=0`, `cp_second_lte_stack=0` in retained log.
- `dumpsys phone` sections not found due to ROM-specific format, not proof of missing phone services.
- `dumpsys isub` yields **three duplicate copies of** `user=LTE_INCLUDED` for each slot. Treat as same repeated policy entry, not three independent proofs; the prior tool assumed per-reason fields unavailable because its parser was insufficient.
- `FRAMEWORK RAF EVENTS: UNAVAILABLE` for `modemRafBitMask / filteredRafBitMask` success path. This *fits* early return on RAF unknown, but could also mean log history lacks success lines.

Source: AOSP `Phone.updateAllowedNetworkTypes`:
```java
int modemRaf = getRadioAccessFamily();
if (modemRaf == RadioAccessFamily.RAF_UNKNOWN) {
    Rlog.d(LOG_TAG, "setPreferredNetworkType: Abort, unknown RAF: " + modemRaf);
    // send GENERIC_FAILURE and return, without setAllowedNetworkTypesBitmap
    return;
}
int filteredRaf = (int) (modemRaf & getEffectiveAllowedNetworkTypes());
mCi.setAllowedNetworkTypesBitmap(filteredRaf, response);
```
Crosschecked https://android.googlesource.com/platform/prebuilts/fullsdk/sources/+/refs/heads/androidx-constraintlayout-release/android-35/com/android/internal/telephony/Phone.java . This code path is in the Android framework, not a `9,9` vendor property.

Samsung HIDL radio bridge `LineageOS/android_hardware_samsung` `hidl/radio/1.3/Radio.cpp` forwards `getRadioCapability(serial)` into `getSecIRadio()`, and `SecRadioResponse.cpp` forwards `getRadioCapabilityResponse(info,rc)` into `radioResponse` without modifying RAF. With the actual vendor binaries, we need data on whether a real `getRadioCapabilityResponse` is absent, invalid, rejected, or stale. **Don't fabricate a capability value or patch a static LTE RAF until CP confirms capability**. Accurate one-slot LTE registration remains unverified.

Locally generated tool `ALICE_A16_RAF_ROOTCAUSE_V2.py` selftested; it now parses numeric RAF from aborts, timestamps, dedups subscription masks, separates abort events from actual `setAllowedNetworkTypesBitmap`, and sanitizes before saving. V2 report required to know whether RAF numeric is truly 0 and whether the abort occurred recently, before any targeted source change.

Never disturb Camera+Video6 branch; no flash-ready LTE image.
