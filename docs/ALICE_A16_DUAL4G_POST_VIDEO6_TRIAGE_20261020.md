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
