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
