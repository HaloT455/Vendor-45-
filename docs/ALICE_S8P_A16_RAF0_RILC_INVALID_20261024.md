# Galaxy S8+ Android16 — RadioCapability RAF=0 root-cause (2026-10-24)

## Confirmed from owner's live device, **both SIMs still inserted**

At 05:31:41–05:31:43 on 2026-10-24, Samsung native RILC emitted `responseRadioCapability: Invalid response` for **BOTH** PHONE0 and PHONE1. Android RILJ then logged `convertHalRadioCapability: ... rat=0 ... rcRil.raf=0` and `Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0`. Returned RadioCapability for both phones has `mRadioAccessFamily=0`. Phone-0 (and Phone-1) then aborted preferred network changes: `setPreferredNetworkType: Abort, unknown RAF: 0`.

Meanwhile both `cmd phone get-allowed-network-types-for-users -s 0` and `-s 1` list LTE. `ro.telephony.default_network=9,9` is already set, but this does **not** bypass missing effective RadioCapability. `gsm.network.type=UMTS,UMTS`; Viettel PHONE0 is OUT_OF_SERVICE for voice and data; MobiFone PHONE1 is IN_SERVICE for voice, OUT_OF_SERVICE for data.

`mMaxActiveDataSubscriptions=2` is framework capability metadata, **not proof of simultaneous real LTE registrations**.

## AOSP mechanistic explanation

- Native [libril/ril_service.cpp](https://android.googlesource.com/platform/hardware/ril/+/22f2df2fa03b0262157b0bf728e48a7828e9b03f/libril/ril_service.cpp) logs `responseRadioCapability: Invalid response` when RIL payload is NULL or its length does not match `sizeof(RIL_RadioCapability)`. This is a failure in the native RIL/HIDL conversion of a legacy Samsung modem response. We do **not** know whether the proprietary modem always responds this way on S8+.
- AOSP [RIL.java](https://android.googlesource.com/platform/frameworks/opt/telephony/+/2244f02d59fc064e9b1083d38761bbf359773c44/src/java/com/android/internal/telephony/RIL.java) builds `makeStaticRadioCapability()` from the **effective runtime framework resource** `android:string/config_radio_access_family` in fallback circumstances. The S8+ actually logs static fallback `using 0`, so fallback capability is not producing a usable nonzero RAF.
- [frameworks/base config.xml](https://android.googlesource.com/platform/frameworks/base/+/7771e3b9b687615a5f72ec3bcfd8a695bb8ede20/core/res/res/values/config.xml) documents `config_radio_access_family` for RILs without `GET_RADIO_CAPABILITY`: supported syntax `GSM|WCDMA|LTE`, etc. The default resource is **empty**.
- [RadioAccessFamily.rafTypeFromString()](https://android.googlesource.com/platform/frameworks/base.git/+/master/telephony/java/android/telephony/RadioAccessFamily.java) maps each canonical uppercase RAT token and fails the entire parse to `RAF_UNKNOWN` when a token is invalid.
- [Phone.java](https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/Phone.java) aborts updating allowed/preferred network types when modem `getRadioAccessFamily()` is unknown (=0).

This leaves **two related issues**: (1) invalid response at native RIL/HIDL boundary, (2) unusable framework static capability fallback. Address (2) if the resource actually resolves empty/malformed on-device, before touching opaque Samsung RIL/CP binaries. Still requires on-device LTE registration confirmation.

## Source Repo: Vendor-45- branch work/a16-sim2-lte-ab-20261023

There is a `vendor/overlay/framework-res__auto_generated_rro_vendor.apk` (33,373-byte original in Test7 vendor image), but its presence does not prove that `config_radio_access_family` is included or enabled.

Read-only audit added: `tools/alice_radio_capability_raf0_audit.py`:

```bash
cd ~/Downloads
curl -fL "https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-sim2-lte-ab-20261023/tools/alice_radio_capability_raf0_audit.py" -o alice_radio_capability_raf0_audit.py
python3 alice_radio_capability_raf0_audit.py --selftest
python3 alice_radio_capability_raf0_audit.py
```

It checks effective Android `config_radio_access_family` for user0/current, sanitizes in-buffer RIL event counts, and reports current voice/data service registration. It makes **no device writes**.

Or run the direct ADB command:

```bash
adb -d shell cmd overlay lookup --user 0 android android:string/config_radio_access_family
adb -d shell cmd overlay lookup --verbose --user 0 android android:string/config_radio_access_family
adb -d shell cmd overlay list --user 0
```

### Next release gate

If the *effective* resource is empty/unrecognized, create a compatible system/framework RRO for `GSM|WCDMA|LTE` based on confirmed owner baseline SIM1 LTE support; verify install status, idmap2, and Phone process restart/boot after a reversible system overlay trial. Do not copy Qualcomm MIUI modem bits. If effective resource is already nonzero but RILJ reports 0, inspect platform resource namespace, phone process initialization and RILJ fallback/parse handling; don't blindly add vendor props.

Native Samsung radio `responseRadioCapability` needs independent compatibility work if the static fallback is not sufficient. No CP/NV/EFS/IMEI change, no claim that camera or 4G+4G is fixed or firmware is ready to flash. Preserve known-booting V12R5T Enforcing boot and video6 vendor baseline.


## Live 17:47 snapshot (user's latest ADB radio-buffer evidence)

```text
Phone-1 : setPreferredNetworkType: Abort, unknown RAF: 0
PhoneSwitcherForMultiSim: mPreferredDataPhoneId = 0,
                         mPrimaryDataSubId = 1, ddsSubId = 1
PhoneSwitcherForMultiSim: updatePreferredDataPhoneId:
                         mPreferredDataPhoneId = 0(PRIMARYDATA)
```

User verified `Logical SIM slot 0: subId=1` (Viettel) and `Logical SIM slot 1: subId=2` (MobiFone); `defaultDataSubId=1`, `activeDataSubId=1`. **This is NOT a failed handoff after choosing MobiFone; no actual data-subscription switch to 2 is evidenced.** PhoneSwitcher is correctly choosing Viettel given DDS=1. The separate `Phone-1` RAF 0 is a reproducible Telephony/RIL compatibility fault, not proof the hardware supports concurrent LTE or the cause of any specific SIM2 attach status.

The user reports Viettel PS/CS WWAN HOME LTE while MobiFone CS WWAN HOME UMTS and PS WWAN NOT_REG_OR_SEARCHING UMTS. S8+ official launch specifications describe its dual-SIM slot as **4G + 3G hybrid**, so Xiaomi Redmi Note 5 Pro Snapdragon 636's 4G+4G upgrade is not transferable without direct Samsung modem evidence. Manufacturer source: https://www.samsung.com/sg/news/local/samsung-announces-availability-of-galaxy-s8-s8plus-and-galaxy-tab-s3-in-singapore/

### Next gated steps — no destructive system change

1. Inspect actual `config_radio_access_family` resource, ideally `adb -d shell cmd overlay lookup --user 0 android android:string/config_radio_access_family`, or execute `tools/alice_radio_capability_raf0_audit.py`.
2. If the resource is empty, **consider a reversible framework-resource overlay** with a capability mask supported by Samsung modem rather than falsely advertising two independently LTE-capable physical stacks. Verify effect on both phones, RIL warning frequency and calling/data.
3. Treat `responseRadioCapability: Invalid response` separately: HAL response packaging can still violate native RIL requirements even if framework static fallback is fixed. Do not patch opaque proprietary RIL/CP without a verified baseline.
4. If user wants to test LTE on SIM2, switch **default data subscription to 2** via privileged Telephony framework or SIM Manager UI; ensure `defaultDataSubId=2`, `activeDataSubId=2`; only then inspect MobiFone PS WWAN LTE. No shell `settings put` shortcut as a substitute for proper `SubscriptionManagerService.setDefaultDataSubId` (requires MODIFY_PHONE_STATE).
5. Never promise or label S8+ 4G+4G hardware achieved based solely on `9,9`, two RadioConfig instances, or an Android overlay. Preserve working V12R5T, camera and Viettel LTE.
