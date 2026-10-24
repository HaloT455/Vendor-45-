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


## Device evidence update — framework RAF resource VALID, overlay ACTIVE

On 2026-10-24 the owner ran:

```text
adb shell cmd overlay lookup --user 0 android android:string/config_radio_access_family
GSM|CDMA|EVDO|WCDMA|LTE

adb shell cmd overlay list --user 0
android
[x] android.auto_generated_rro_vendor__
[x] android.auto_generated_rro_product__
```

**This FALSIFIES the earlier hypothesis that the effective Android framework overlay is missing, empty or contains an unrecognized RAF token.** These five tokens are all recognized by AOSP `RadioAccessFamily.rafTypeFromString()` and should map to a nonzero mask. Replacing the existing overlay with another `GSM|WCDMA|LTE` RRO would NOT be an evidence-based fix. Neither `ro.telephony.default_network=9,9` nor the per-slot USER LTE mask should be changed.

Two `adb: no devices found` replies immediately before the successful lookup were transient ADB visibility failures; later successful commands demonstrate that they are not evidence of a permanent radio problem.

The earlier `Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0` was logged at 05:31:41, whereas the **valid effective overlay lookup was later**, so it is not yet proven that the same resource value was effective when `RILJ` constructed the cached static RadioCapability on startup. At 17:47 the user still observed `Phone-1 setPreferredNetworkType: Abort, unknown RAF: 0` while both carriers were registered for voice and Viettel LTE was live. AOSP's `RIL.makeStaticRadioCapability` fetches `config_radio_access_family` from resources *at invocation*, not from the shell's live overlay display. State cached by `Phone` may differ if resources or the phone process changed in between; verify that before making changes.

**Next safest diagnostic (read-only):**

```bash
echo '===== EFFECTIVE RAF CONFIG ====='
adb -d shell cmd overlay lookup --user 0 android android:string/config_radio_access_family

echo '===== CURRENT PHONE CAPABILITY (SANITIZED) ====='
adb -d shell dumpsys phone | grep -iE 'mRadioCapability|RadioCapability|mRadioAccessFamily|mPhoneId' | tail -35

echo '===== GET CAPABILITY FAILURES (RECENT LOG BUFFER) ====='
adb -d shell 'logcat -b radio -d -t 5000' |
grep -iE 'responseRadioCapability: Invalid response|Faking RIL_REQUEST_GET_RADIO_CAPABILITY|unknown RAF' |
tail -25
```

Do not print full `dumpsys phone` (it can contain subscriber identifiers). Do not claim simultaneous LTE; an LTE attachment on SIM1 while SIM2 reports CS UMTS/PS UMTS NOT_REG_OR_SEARCHING is still LTE+UMTS. Next relevant *functional* test requires an observed switch from defaultDataSubId=1 (Viettel) to 2 (MobiFone) before evaluating LTE handoff; launching a Settings screen alone is not a switch.

Any proposed native RIL/HIDL repair must respect Android's RIL_RadioCapability payload layout. AOSP `libril/ril_service.cpp` emits `responseRadioCapability: Invalid response` if `response == NULL` OR `responseLen != sizeof(RIL_RadioCapability)`. Without details of proprietary Samsung RIL return/error/payload, **no safe flash-ready binary patch has been demonstrated**. Do not manufacture a radio capability or flash Qualcomm modem firmware.

AOSP references:
- https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/telephony/java/android/telephony/RadioAccessFamily.java
- https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/RIL.java
- https://android.googlesource.com/platform/hardware/ril/+/0a0f220a983b866017c00dc5211c7bf8aa32a852/libril/ril_service.cpp


## Follow-up after live ROM RAF resource check (2026-10-24)

Owner's output:

```text
FRAMEWORK: GSM|CDMA|EVDO|WCDMA|LTE
dumpsys phone | grep -iE 'mRadioCapability|mRadioAccessFamily|RadioCapability'  => NO MATCH
logcat -b radio -d -t 5000 ... =>
  17:47:12 Phone-1 setPreferredNetworkType: Abort, unknown RAF: 0
  17:47:14 Phone-1 setPreferredNetworkType: Abort, unknown RAF: 0
```

Interpretation:
- These are **replayed buffer lines**: absence of a new `Invalid response` in the short selected window does **not** establish that Samsung RIL has become compliant.
- An empty grep over `dumpsys phone` provides **no positive evidence** that `Phone.mRadioCapability` has a valid nonzero mask. AOSP `Phone.getRadioAccessFamily()` reads the cached `mRadioCapability` and the `updateAllowedNetworkTypes` path immediately aborts when this mask is 0. Reference: https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/Phone.java
- An effective valid `cmd overlay lookup` value rules out the **live resource overlay content** as the fault, but does **not** prove what was loaded at the time the earlier `RIL.makeStaticRadioCapability()` constructed the `RAF=0` fallback.
- **No build/flash patch yet:** A safe framework-side compatibility fix would need the actual Android 16 system/framework sources and correct overlay/package context; the vendor repository alone cannot directly patch the Java `Phone` object. Guessing a replacement RAF capability that exceeds actual Exynos8895 support is unacceptable.
- The current device is proven LTE(PS HOME) on Viettel slot0 and UMTS(CS HOME, PS NOT_REG_OR_SEARCHING) on MobiFone slot1. The data subscription mapping remains `subId=1` Viettel, `subId=2` MobiFone, `defaultDataSubId=1`, `activeDataSubId=1`. No successful switch to MobiFone default data has been observed. Therefore, no claim of handoff failure or Dual 4G on the actual device.
- Do not override RadioCapability or change RAF mask to force both LTE. Maintain working 4G Viettel, MobiFone 3G, camera/video.


## Implemented source-only opt-in Phone1 RAF0 fallback candidate (2026-10-24)

Added:
- \`patches/android16/0001-Phone-optional-S8Plus-phone1-RAF0-framework-fallback.patch\`
- \`tools/test_android16_phone_raf0_trial_patch.py\`
- upgraded \`tools/alice_sim2_lte_handoff_probe.py\` to parse \`Logical SIM slot N: subId=M\` and independently assess \`CS/PS WWAN\` RAT/registration, **not** IWLAN.
- CI selftest for the patch, parsing and snapshots.

**Candidate fix mechanism:** In a compatible Android16 \`frameworks/opt/telephony\` source checkout, the patch guards \`Phone.updateAllowedNetworkTypes()\` against *Phone1* cached \`RAF_UNKNOWN=0\`. It uses only \`android:string/config_radio_access_family\` (currently confirmed \`GSM|CDMA|EVDO|WCDMA|LTE\`) as fallback, rather than fabricating Qualcomm modem information. It is gated by the **default-disabled** device property \`persist.vendor.alice.s8p_raf0_fallback\` and by \`getPhoneId()==1\`. Phone0 is not modified in behavior. When disabled (default), patched behavior is identical to AOSP.

This fixes only the **framework pre-RIL abort branch** on an opt-in build; it does **NOT** repair native Samsung \`responseRadioCapability: Invalid response\`, it is not proof of two LTE physical stacks, and it cannot generate independent LTE bearers on CP hardware that doesn't have them. The built system framework could have different source layout/Telephony classes; patch applicability must be verified against the **exact running ROM source**.

**Apply to a full ROM source checkout only, not to the existing Vendor tree as a fake binary:**

\`\`\`bash
cd /path/to/android16/frameworks/opt/telephony
git apply --check /path/to/Vendor-45-/patches/android16/0001-Phone-optional-S8Plus-phone1-RAF0-framework-fallback.patch
git apply /path/to/Vendor-45-/patches/android16/0001-Phone-optional-S8Plus-phone1-RAF0-framework-fallback.patch
# Then build the matching Telephony/ROM targets and run CTS/telephony tests.
# Do NOT turn on the property or flash an unverified image.
\`\`\`

In the Vendor repository, offline validation can be run as:

\`\`\`bash
python3 tools/alice_sim2_lte_handoff_probe.py --selftest
python3 tools/test_android16_phone_raf0_trial_patch.py
\`\`\`

**Release gate:** The repository DOES NOT include the current phone's matching framework source, so the Phone.java patch has NOT been applied to the owner's phone system image and has NOT been compiled into flashable \`boot.img\`, \`vendor.img\`, or a full ROM. Neither kernel driver nor Samsung proprietary RIL has been changed. Preserve the working V12R5T boot and camera/video. Independently confirm an actual DDS switch \`defaultDataSubId=2\` and \`activeDataSubId=2\` before claiming handoff was repaired.

The authoritative Redmi Note5 Pro MIUI Dual4G release relied on Snapdragon-supported modem firmware; this source patch is a **limited Android Telephony compatibility experiment**, not a Qualcomm firmware transplant.


## 2026-10-24 confirmed parser vs cached RAF and both-phone RIL fallback experiment

**Real phone output, direct root app_process (NOT simulation)**:
\`\`\`text
ALICE_CACHED_RAF: phoneId=0 decimal=0 hex=0x0 LTE_BIT_4096=false
ALICE_CACHED_RAF: phoneId=1 decimal=0 hex=0x0 LTE_BIT_4096=false
ALICE_RAF_PARSE_CANONICAL: decimal=64508 hex=0xfbfc LTE_BIT_4096=true
ALICE_RAF_RUNTIME_RESOURCE: GSM|CDMA|EVDO|WCDMA|LTE
ALICE_RAF_PARSE_RUNTIME: decimal=64508 hex=0xfbfc LTE_BIT_4096=true
\`\`\`

The parser and the new app_process \`Resources.getSystem()\` are correct. Both cached \`Phone.mRadioCapability.raf=0\` remain incorrect/inconsistent with **Viettel registered PS WWAN LTE**. This is a Telephony RIL capability reporting/caching compatibility defect. It is **not a claim that S8+ can run LTE simultaneously on both SIMs**.

For DDS handoff, the 22:10 A/B test proved \`setDefaultDataSubId(2)\` and \`activeDataSubId=2\` succeed, PhoneSwitcher says \`DDS change success, PhoneId : 1\`, while phone1 MobiFone registers **HSUPA**, not LTE. \`ProxyController: setRadioCapability: Already in requested configuration\` is consistent with both requested and cached RAF values being 0.

**New candidate source patch**: \`patches/android16/0002-RIL-S8Plus-both-phones-RAF0-resource-fallback-OPTIN.patch\` changes the **AOSP \`RIL.makeStaticRadioCapability()\`** fallback for both slots, not Phone1 alone. When the original \`mContext.getResources().getString(config_radio_access_family)\` parses to RAF_UNKNOWN, this S8+ opt-in trial reads **the actual same framework resource from \`Resources.getSystem()\`**, which the owner's app_process just confirmed parses to 64508. Only uses a nonzero parsed result, and does not hardcode / spoof a raw 4G+4G per-slot modem response.

Guards: requires \`ro.product.vendor.device=dream2lte\`, explicit \`persist.vendor.alice.s8p_raf0_resource_fallback=true\`, both disabled on other models and **off by default**. Does not edit CP/EFS, boot, vendor binaries, RIL HAL response ABI, or force a \`RadioCapability.set\` transaction. This will not fix malformed **native** \`responseRadioCapability()\` payload; it addresses only the AOSP static-fallback path when invoked and when its context resource is zero. It is not guaranteed to get LTE on SIM2 or give two LTE stacks concurrently.

CI offline selftest: \`python3 tools/test_android16_ril_raf0_resource_fallback.py\` runs GNU patch against an AOSP-shaped RIL.java fixture and asserts the device gate, opt-in default FALSE, no hardcoded network mode or CP/EFS writes. **CI PASS not yet verified; real ROM compilation and on-device impact NOT performed.**

**Critical source integration restriction**: \`Vendor-45-\` and \`dream2lte-45\` do NOT supply the *running* Android16 \`frameworks/opt/telephony\` \`RIL.java\`, so this patch cannot be embedded into just vendor.img or boot.img. A user must identify and build their ROM's own matching Telephony framework; only then can a guarded ROM test build, backed up with a tested rollback, be considered. Installing a source patch in the vendor tree does NOT alter the RIL on the user's phone. Do not tell the user to flash the source patch or claim dual 4G success.

Avoid enabling this workaround by \`setprop\` on a stock binary where no patch exists. Merely setting the property has no effect; introducing unregistered persist.vendor properties may violate SELinux property_contexts.

Reference AOSP source:
- \`RIL.makeStaticRadioCapability\`: https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/RIL.java
- \`Phone.getRadioAccessFamily\`: https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/Phone.java
- \`ProxyController.setRadioCapability\`: https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/main/src/java/com/android/internal/telephony/ProxyController.java


## 2026-10-24 ROM fingerprint: Samsung Galaxy S22 GZD7 Android16 identity

Owner's **real S8+ dream2lte** returned:
\`\`\`text
ro.build.display.id=BP2A.250605.031.A3.S901BXXSNGZD7
ro.build.version.release=16
ro.build.fingerprint=samsung/r0sxxx/r0s:16/BP2A.250605.031.A3/S901BXXSNGZD7:user/release-keys
pm path com.android.phone=package:/system/priv-app/TeleService/TeleService.apk
\`\`\`

**Cross-verification:** Samsung's official Galaxy S22 (SM-S901B) firmware changelog identifies \`S901BXXSNGZD7\` as an **Android16** release published 2026-05-27:
https://doc.samsungmobile.com/SM-S901B/021718220304/eng.html
LineageOS device wiki confirms \`r0s\` is Galaxy S22 Exynos2200:
https://github.com/LineageOS/lineage_wiki/blob/main/_data/devices/r0s.yml

**Interpretation:** The device is physically S8+ Exynos8895 (owner's independent \`ro.product.vendor.device=dream2lte\`, boot kernel 4.4 Alice, radio CP G955F) but the Android system advertises a Galaxy S22 firmware identity. This is consistent with a Samsung OneUI8 port or build-fingerprint impersonation; it **does not prove** every runtime system/framework artifact was sourced unchanged from S22 firmware nor identify the custom ROM tree/maintainer.

\`TeleService.apk\` is the \`com.android.phone\` Android privileged application path, **not automatically the JAR containing \`com.android.internal.telephony.RIL\`**. That source traditionally builds as \`telephony-common.jar\`, possibly with ART oat/vdex or OEM-modified class loading. Need inspect installed runtime Java classpaths and framework jar inventories before attempting smali/dex transformations.

A safe read-only on-device provenance check:
\`\`\`bash
adb -d shell '
echo "===== DEVICE VS SYSTEM ====="
getprop ro.product.vendor.device
getprop ro.product.device
getprop ro.build.display.id
echo "===== TELEPHONY PACKAGES ====="
pm path com.android.phone
echo "===== FRAMEWORK JAR FILES ====="
for x in /system/framework/telephony-common.jar /system_ext/framework/telephony-common.jar /system/framework/services.jar /system/priv-app/TeleService/TeleService.apk; do
  [ -e "$x" ] && ls -l "$x"
done
echo "===== BOOT CLASSPATH TELEPHONY ENTRIES ====="
printf "%s\n" "$BOOTCLASSPATH" | tr ":" "\n" | grep -Ei "telephony|framework|services" | head -30
'
\`\`\`

**No proof that the exact matching Samsung OneUI8 Telephony source is publicly released or built in current Vendor/Kernel repos.** Do not replace \`TeleService.apk\` just because \`pm path\` shows it; replacing signed Samsung apps/core framework JARs on a working phone risks zygote/phone-process bootloop and loss of mobile connectivity. The current source-only RIL fallback trial cannot be packaged into a flash-ready boot/vendor without matching framework build. The stable S8+ camera/video and 4G Viettel should be preserved.


## Verified real ROM framework path and safe binary capture (S8+, 2026-10-24)

Owner's LIVE read-only ADB output from OneUI8 Android16 S8+:
\`\`\`text
ro.product.vendor.device=dream2lte
ro.product.device=r0s
uname -r=4.4.302-Alice-V12R5T-MGLRU-KSU32590-Enf+
/system/framework/telephony-common.jar  6.2M
/system/framework/services.jar          24M
/system/priv-app/TeleService/TeleService.apk 7.9M
BOOTCLASSPATH includes /system/framework/telephony-common.jar
\`\`\`

**Most likely executable target is the actual current system \`telephony-common.jar\`, NOT \`TeleService.apk\` nor kernel/vendor partitions.** However the JAR's DEX must be inspected to prove \`com.android.internal.telephony.RIL\`, \`Phone\`, \`ProxyController\` and \`RIL.makeStaticRadioCapability\` actually exist, because OEM ports vary. A BOOTCLASSPATH entry establishes the file's role, not that its DEX methods match current open-source AOSP.

Added \`tools/android16/alice_pull_telephony_framework.py\` at Vendor commit \`4baad44eb6338d38b782fa25e5ba05342abdd824\`, which **only** ADB pulls \`/system/framework/telephony-common.jar\` to Linux, prints SHA256, enumerates \`classes*.dex\` and checks method/class descriptors as binary string presence. It has no root or phone writes. Selftest is in Vendor CI. The byte-string inventory is not source decompilation.

Linux command:
\`\`\`bash
cd ~/Downloads
curl -fL "https://raw.githubusercontent.com/HaloT455/Vendor-45-/4baad44eb6338d38b782fa25e5ba05342abdd824/tools/android16/alice_pull_telephony_framework.py" -o alice_pull_telephony_framework.py
python3 alice_pull_telephony_framework.py --selftest
python3 alice_pull_telephony_framework.py --out "$HOME/Downloads/ALICE_ROM_RADIO_DUMP"
\`\`\`

If \`RIL\` or \`makeStaticRadioCapability\` is missing, inspect class location in other framework jars rather than trying to patch nonexisting methods. If present, compare decompiled ROM-specific RIL.java and GET_RADIO_CAPABILITY callback handling to the opt-in candidate patch before requesting a ROM-compatible rebuilt JAR. Any boot-classpath replacement can cause severe bootloop even with valid dex; it requires exact signatures, verified dexopt/hidden API/core runtime compatibility and **tested recovery** before installation.

NO flash-ready or tested Android16 telephony jar is available yet; source-only RIL.patch remains OFF by default. No evidence confirms simultaneous Exynos8895 Dual LTE. Preserve LTE Viettel/HSUPA MobiFone and stable camera/video.


## EXACT S8+ telephony-common.jar captured on real Android16 (2026-10-24)

The owner **successfully pulled** the real \`/system/framework/telephony-common.jar\` from Galaxy S8+ to ThinkPad using the read-only ALICE inventory tool, with:
\`\`\`text
ALICE_JAR_CAPTURE: /home/halo-pmf/Downloads/ALICE_ROM_RADIO_DUMP/telephony-common.jar
ALICE_JAR_BYTES: 6525408
ALICE_JAR_SHA256: 8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1
ALICE_JAR_DEX_FILES: classes.dex
ALICE_DEX_CLASS_RIL: PRESENT
ALICE_DEX_CLASS_Phone: PRESENT
ALICE_DEX_CLASS_ProxyController: PRESENT
ALICE_DEX_CLASS_RadioCapability: PRESENT
ALICE_DEX_NAME_makeStaticRadioCapability: PRESENT
ALICE_DEX_NAME_getRadioAccessFamily: PRESENT
ALICE_DEX_NAME_setRadioCapability: PRESENT
ALICE_DEX_NAME_updateAllowedNetworkTypes: PRESENT
\`\`\`
This **proves the DEX contains these strings/descriptors, NOT the exact method bodies or their class membership**. Do not extrapolate from class strings alone; decompile the exact binary next. No file from the owner's phone has been uploaded to GitHub or to this chat.

**New reproducible read-only source-level inspection:**
\`tools/android16/alice_decompile_telephony_raf.py\`, commit \`699339d75d099c9d99dd79ec76e0dee48ea4ce18\`.
It pins the exact SHA256 above before accepting input; invokes official JADX v1.5.6 CLI with \`--single-class\` on \`RIL\`, \`Phone\`, \`ProxyController\` and locally saves Java-source reconstructions plus bounded \`ALICE_RAF_METHOD_EXCERPTS.txt\`. Java reconstruction is heuristic; a JADX decoding failure must NOT be interpreted as absence of a method. The tool does not patch/replace system JAR, run adb, or change CP/EFS.

Official JADX: https://github.com/skylot/jadx/releases/tag/v1.5.6

Steps on owner's ThinkPad:
\`\`\`bash
cd ~/Downloads
curl -fL --retry 3 "https://github.com/skylot/jadx/releases/download/v1.5.6/jadx-1.5.6.zip" -o jadx-1.5.6.zip
mkdir -p jadx-1.5.6
unzip -oq jadx-1.5.6.zip -d jadx-1.5.6
curl -fL "https://raw.githubusercontent.com/HaloT455/Vendor-45-/699339d75d099c9d99dd79ec76e0dee48ea4ce18/tools/android16/alice_decompile_telephony_raf.py" -o alice_decompile_telephony_raf.py
python3 alice_decompile_telephony_raf.py --selftest
python3 alice_decompile_telephony_raf.py --jadx "$HOME/Downloads/jadx-1.5.6/bin/jadx" --jar "$HOME/Downloads/ALICE_ROM_RADIO_DUMP/telephony-common.jar" --out "$HOME/Downloads/ALICE_ROM_RADIO_DUMP/raf_decompiled"
\`\`\`
If JADX executable has no +x bit: run \`chmod +x ~/Downloads/jadx-1.5.6/bin/jadx\` after confirming this is official archive. The report is local at \`~/Downloads/ALICE_ROM_RADIO_DUMP/raf_decompiled/ALICE_RAF_METHOD_EXCERPTS.txt\`. No modem-change/flash instruction is issued.

**AOSP comparison anchors:**
- \`RIL.makeStaticRadioCapability\`: how the context config resource feeds the zero/nonzero fallback RAF.
- \`RIL.processResponse\` / \`getRadioCapability\`: whether the Samsung legacy RIL error falls back to a static object and what error conditions invoke it.
- \`Phone.getRadioAccessFamily\`, \`Phone.updateAllowedNetworkTypes\`: which cached Phone RadioCapability becomes 0 and how it blocks RAT updates.
- \`ProxyController.setRadioCapability\`: why both RAF=0 caused \`Already in requested configuration\` at DDS switch.

**Patch-quality gates:** The current \`0002-RIL...\` is a **source-only AOSP-shaped experimental trial**, not yet verified against these actual OEM Decompiled method bodies. Do NOT build or flash a system JAR until the exact method signature and control flow are checked, a compatible ROM build environment is available, and a recovery/rollback mechanism is tested. Preserve working S8+ Viettel LTE, MobiFone HSUPA/UMTS, camera/video, boot V12R5T, proprietary modem.


## 2026-10-24 REAL JADX RIL MAKESTATIC HARD-CODED ZERO CONFIRMED

Owner decompiled the **exact** \`/system/framework/telephony-common.jar\` (6525408 bytes,
SHA256 \`8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1\`)
with JADX 1.5.6 and shared \`ALICE_RAF_METHOD_EXCERPTS.txt\`.

Real Samsung/OneUI8 \`com.android.internal.telephony.RIL.java\`, decompiled line 2656:
\`\`\`java
RadioCapability makeStaticRadioCapability() {
    RadioCapability radioCapability = new RadioCapability(this.mPhoneId.intValue(), 0, 0, 0, PhoneConfigurationManager.SSSS, 1);
    riljLog("Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0");
    return radioCapability;
}
\`\`\`

**This is decisive:** the ROM's Java fallback explicitly hardcodes RAF=0 for **both** phone IDs, rather than parsing \`config_radio_access_family\`. It is *not* merely a missing runtime resource. When this fallback is used after invalid Samsung native GET_RADIO_CAPABILITY responses, cached per-phone RAF=0 is consistent with owner-verified \`ITelephony.getRadioAccessFamily(0)=0\` and \`getRadioAccessFamily(1)=0\`. The owner independently verified \`Resources.getSystem().getString(config_radio_access_family)=GSM|CDMA|EVDO|WCDMA|LTE\` parses to 64508 (0xFBFC) in a separate app_process. Hence fixing only config RRO or USER allowed LTE bits is ineffective; those values are already valid.

Real decompiled \`Phone.java\`:
\`\`\`java
public int getRadioAccessFamily() {
    RadioCapability radioCapability = getRadioCapability();
    if (radioCapability == null) return 0;
    return radioCapability.getRadioAccessFamily();
}
protected void updateAllowedNetworkTypes(Message message) {
    int radioAccessFamily = getRadioAccessFamily();
    if (radioAccessFamily == 0) {
       Rlog.d(this.mLogTag, "setPreferredNetworkType: Abort, unknown RAF: " + radioAccessFamily);
       // replies GENERIC_FAILURE and returns early
       ...
    }
    // otherwise filters allowed network types against modem RAF
}
\`\`\`
Real \`ProxyController.getMaxRafSupported()\`/min returns 0 when both phones RAF=0, and \`ProxyController.setRadioCapability()\` returns true without transaction when requested RAFs already match those current cached 0 values. This matches 22:10 live log \`setRadioCapability: Already in requested configuration, nothing to do.\`

**Updated experiment matching REAL decompiled method**: \`patches/android16/0003-S8Plus-OneUI8-RIL-REAL-METHOD-RAF0-FALLBACK-OPTIN.patch\`. Replaces the hardcoded \`new RadioCapability(..., 0, ...)\` *fallback* method with guarded \`Resources.getSystem()\` parsing and nonzero RAF only for \`ro.product.vendor.device=dream2lte\` **and** \`persist.vendor.alice.s8p_raf0_resource_fallback=true\`. Default FALSE for safety. \`tools/test_s8p_real_rom_ril_raf0_patch.py\` validates against the exact five-line decompiled method fixture, not the outdated open-source RIL snippet. The two older experimental patches 0001 (Phone1 only) and 0002 (AOSP RIL method, not matching Samsung method) are SUPERSEDED as solutions for this particular port; do not apply either directly to S8+ system.

**Strict constraints**: The JADX Java text is **not** compilable ROM source simply because it was decompiled. The new file is a *source-level proposal*, not an in-place patch to \`classes.dex\`. No verified smali/baksmali surgical DEX editing, no replacement JAR, no system/framework flashing. Because this is a BOOTCLASSPATH JAR, installing an untested rebuild can bootloop or disrupt radio; before any real-world installation need exact method-level smali from the same original SHA, same signing/ART format expectations, offline DEX reassembly and verification, **and tested recovery/rollback**. On a patched ROM, on-device property_contexts/SELinux handling for the optional persist.vendor property must also be defined if opt-in mode is enabled. Direct \`setprop\` alone cannot change stock bytecode and should not be used as a purported fix.

**Not a Dual 4G guarantee:** Giving both Phones fallback RAF=64508 may make both identical; the ProxyController's *maximum/minimum* still cannot infer the modem's actual stronger/weaker radio-stack capability from identical values, and a real \`setRadioCapability\` exchange may remain unsupported by proprietary Exynos8895 RIL. This repairs a proven **framework fallback bug** only if compiled/applied, not OEM RF hardware limitations. Manufacturer original S8+ Dual SIM spec was 4G+3G.


## Actual uploaded BOOTCLASSPATH JAR / byte-accurate DEX verification

Owner directly attached the original 6,525,408-byte `telephony-common.jar`. The exact uploaded binary was analyzed locally:
```text
JAR SHA256 8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1
classes.dex length 6117656, version dex/039
DEX internal SHA1 VALID; internal Adler32 VALID
Lcom/android/internal/telephony/RIL;->makeStaticRadioCapability():
  code_item_off = 3408124
  registers_size=8, ins_size=1, outs_size=7, tries_size=0, insns_size=38 (16-bit words)
  DEX byte off 3408166: 12 04 = Dalvik const/4 v4, #+0
  invoke-direct/range {v0 .. v6},
    Lcom/android/internal/telephony/RadioCapability;-><init>(IIIILjava/lang/String;I)V
  v4 is the fourth int constructor parameter: cached Radio Access Family
```
This is **byte-level verification**, not just JADX output.

The actual DEX has `Resources.getSystem` method reference, but DOES NOT contain a method reference to `RadioAccessFamily.rafTypeFromString` or the literal string `config_radio_access_family`. Therefore an in-place *literal-only* 2-byte modification cannot implement the desired gated, system-resource-derived fallback. A high-quality fix would require rebuilding/reassembling the relevant DEX with additional method and string references and verifying runtime ART compatibility. Merely forcing a constant LTE mask risks misrepresenting true proprietary modem capabilities; do not offer that as a validated fix or claim Dual-4G.

Produced owner-facing **offline-only audit bundle** with (a) exact DEX checksum/offset metadata, (b) source-only candidate Smali method guarded by dream2lte + default-off property, (c) explicit no-flash status and recovery prerequisites. The original JAR on the phone was not touched, and **no flash-ready replacement telephony-common.jar** was fabricated. The draft Smali candidate has not been assembled/disassembled or tested on hardware, so it is not a deployable patch.

Even a successfully assembled corrected `RIL.makeStaticRadioCapability` would only help when that fallback method is actually invoked, and would not prove 4G+4G on Exynos8895.


## 2026-10-25 real Smali 3.0.10 roundtrip: disassembly PASS, API36 unsupported; select 29 for original DEX039

The user ran \`ALICE_S8P_RAF0_OFFLINE_ROUNDTRIP.sh\` on a Linux host. Verified:
- Original \`telephony-common.jar\` passed SHA256 \`8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1\`.
- Both v3.0.10 fat JAR tool binaries downloaded and passed official SHA256.
- \`baksmali ... --api 36\` **succeeded** and disassembled the actual RIL fallback method.
- Exact real Smali method:
\`\`\`smali
.method greylist-max-r makeStaticRadioCapability()Lcom/android/internal/telephony/RadioCapability;
    .registers 8
    new-instance v0, Lcom/android/internal/telephony/RadioCapability;
    iget-object v1, p0, Lcom/android/internal/telephony/RIL;->mPhoneId:Ljava/lang/Integer;
    invoke-virtual {v1}, Ljava/lang/Integer;->intValue()I
    move-result v1
    const-string v5, ""
    const/4 v6, 0x1
    const/4 v2, 0x0
    const/4 v3, 0x0
    const/4 v4, 0x0
    invoke-direct/range {v0 .. v6}, Lcom/android/internal/telephony/RadioCapability;-><init>(IIIILjava/lang/String;I)V
    # ... logs "Faking ... using " + v4; return v0
.end method
\`\`\`
This independently verifies \`v4=0\` is passed to the fourth \`RadioCapability\` constructor parameter, the cached RAF bit mask.

**Real failed step:** \`java -jar smali-3.0.10-fat-release.jar assemble --api 36 ...\` threw:
\`\`\`text
java.lang.IllegalArgumentException: dexVersion must be within [0, 999]
  at com.android.tools.smali.dexlib2.dexbacked.raw.HeaderItem.getMagicForDexVersion
\`\`\`
Root cause checked in \`google/smali\` tag \`3.0.10\`:
\`VersionMap.mapApiToDexVersion(36)\` returns \`NO_VERSION=-1\` (supports at most API35); creating DEX header from -1 throws. This is **a tool-version mapping error, not a ROM/framework failure**. The real uploaded \`classes.dex\` header is **\`dex\\n039\\0\`**, i.e. DEX 039, matching Smali \`--api 29\`. Use \`--api 29\` for **both** disassemble and assemble in a reproducible offline roundtrip, and assert output DEX header stays 039. \`--api 35\` would write DEX 041 and alter the source's format.

Local diagnostic:
\`\`\`bash
sed -i 's/--api 36/--api 29/g' ~/Downloads/ALICE_S8P_RAF0_OFFLINE_ROUNDTRIP.sh
bash ~/Downloads/ALICE_S8P_RAF0_OFFLINE_ROUNDTRIP.sh
\`\`\`
A V3 script generated in the conversation additionally validates original and output DEX039 headers. **No actual roundtrip success reported yet**; offline DEX checksum pass would show internal structural consistency only, NOT verification by on-device ART or safe replacement of the BOOTCLASSPATH JAR.

Source mapping: https://github.com/google/smali/blob/3.0.10/dexlib2/src/main/java/com/android/tools/smali/dexlib2/VersionMap.java . Never flash compiled DEX into phone at this point.


## S8+ confirmed full Smali/DEX roundtrip with API 29 (2026-10-25)

Owner's ThinkPad log confirmed: \`telephony-common.jar\` expected SHA256 \`8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1\` PASS; official smali/baksmali v3.0.10 downloads and SHA-256 checks PASS; \`baksmali disassemble --api 29\` successfully extracted the exact OEM \`RIL.makeStaticRadioCapability()\` method, and \`smali assemble --api 29\` successfully round-tripped the **ENTIRE UNMODIFIED ROM DEX**.

Owner's outcome:
\`\`\`text
PASS: offline roundtrip DEX integrity 6117656 bytes
ROUNDTRIP SHA256: 4acc0950271732f8ef1d1730896963617ac4bc4da165d5010e101105344c2d42
COMPLETE: NO ON-DEVICE CHANGES
\`\`\`

The original \`classes.dex\` uses DEX header \`039\`; official smali v3.0.10 \`VersionMap.mapApiToDexVersion(36)\` returns NO_VERSION(-1), so \`--api 36\` causes \`dexVersion must be within [0,999]\`. Using **\`--api 29\`** for DEX039 roundtrip fixes the tool version-map error; it **does not downgrade Android16** and is not a proof of ART bootclasspath compatibility.

The exact original SMALI demonstrates:
\`\`\`smali
.method greylist-max-r makeStaticRadioCapability()Lcom/android/internal/telephony/RadioCapability;
    .registers 8
    ...
    const/4 v4, 0x0
    invoke-direct/range {v0 .. v6}, Lcom/android/internal/telephony/RadioCapability;-><init>(IIIILjava/lang/String;I)V
    ...
.end method
\`\`\`
This proves \`v4\` (the 4th \`I\` constructor argument) is initialized to **zero** in the ROM's RIL fallback. No patched DEX or repaired phone behavior has yet been validated.

Current follow-up is an **offline-only experimental Smali candidate**, guarded by \`ro.product.vendor.device=dream2lte\` and default-OFF \`persist.vendor.alice.s8p_raf0_resource_fallback\`; it reads \`Resources.getSystem().getIdentifier("config_radio_access_family", "string", "android")\` and \`android.telephony.RadioAccessFamily.rafTypeFromString\`, only when explicitly enabled. The local script \`ALICE_S8P_RAF0_SMALI_OFFLINE_TRIAL.sh\` produces \`classes.raf0-OFFLINE-DO-NOT-FLASH.dex\` under \`~/Downloads/ALICE_ROM_RADIO_DUMP/raf0-offline\`, and round-trip re-disassembles the candidate to check the intended method survived assembly. It **does not build a flashable JAR or write to the phone**; no ART install test, SELinux property context validation or tested rollback. Do not instruct flashing this DEX to the S8+.

The fallback RAF \`64508 (0xFBFC)\` from valid system resource expresses software-configured RAT *options*, not modem support for concurrent 4G+4G. Even if patched framework caches nonzero RAF, the Exynos8895/Samsung RIL might only support one LTE registration at a time, and \`ProxyController.getMax/MinRafSupported\` may see equal masks instead of correct per-stack caps.


## 2026-10-25 first complete ROM DEX RAF0 offline Smali assembly PASS

Owner ran \`ALICE_S8P_RAF0_SMALI_OFFLINE_TRIAL.sh\` on ThinkPad and supplied actual output:
\`\`\`text
/home/halo-pmf/Downloads/ALICE_ROM_RADIO_DUMP/telephony-common.jar: OK
PASS: source-only change limited to exact RIL.makeStaticRadioCapability()
PATCH DIFF: /home/halo-pmf/Downloads/ALICE_ROM_RADIO_DUMP/raf0-trial-smali/ALICE_RAF0_METHOD_DIFF.txt
===== COMPILE RAF0 TRIAL DEX OFFLINE =====
===== DEX HEADER / CHECKSUM / STRINGS =====
PASS: offline trial DEX checksum, DEX039 and patch string markers
SHA256: c1a641b18d92a28dd2c3f25a7930febc91e97d2199fb434e42726360b042a0e4
DEX bytes: 6117972
===== RE-DISASSEMBLE FOR VERIFY =====
PASS: patch references survived assemble / disassemble
WARNING: this does NOT verify Android ART bootclasspath startup or radio stability
===== OFFLINE COMPLETE - NO DEVICE CHANGES =====
\`\`\`

The base \`classes.dex\` was 6,117,656 bytes and the candidate is 6,117,972 bytes; +316 bytes is plausible for one method's new device/property/resource conditional path and added string constants. **A signed, bootclasspath-correct, phone-tested flashable JAR does not yet exist.** The changed DEX SHA-256 simply identifies the offline experiment; it is not a stability/safety attestation. Real UART/radio RIL still unmodified on the phone.

The proven initial full unmodified roundtrip occurred after selecting \`--api 29\` (DEX 039); Smali 3.0.10's VersionMap does NOT map Android API 36 and \`--api 36\` fails with \`dexVersion must be within [0,999]\`. DEX 039 encoding is a *file-format* decision, not downgrading the Android ROM.

Next safety gate: perform a strict, offline, class-by-class Smali diff of the ORIGINAL Baksmali dump \`$HOME/Downloads/ALICE_ROM_RADIO_DUMP/raf0-offline/smali\` vs roundtripped patched Smali \`.../raf0-offline/raf0-reverify\`, allowing only the \`RIL.makeStaticRadioCapability()\` body and rejecting class membership or unrelated method changes. Also verify original and trial checksum, class/field/prototype ID counts. If any unrelated differences, STOP rather than flashing. A check of boot-time ART verifier, property access and recovery is still required even after strict structural diff.

A standalone script \`ALICE_S8P_RAF0_STRICT_DEX_DIFF.py\` has been generated in the conversation artifact sandbox with known owner-file hashes and a passing *fixture selftest*, but has **not yet been run against the owner's actual disassembled Smali trees**. No results from that full comparison should be claimed until owner runs it and supplies output.

Safeguard: the Smali experiment's \`persist.vendor.alice.s8p_raf0_resource_fallback\` guard defaults to false. Enabling this property on an unmodified ROM has no effect; on modified bootclasspath ROM may require proper SELinux property_contexts handling. It is also possible for the proprietary Exynos8895 modem/RIL not to support dual independent LTE even when Java framework RAF=64508. Preserve original telephony-common.jar SHA \`8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1\` and kernel 4.4.302-Alice-V12R5T.


## 2026-10-25 strict offline Smali diff PASS: 3628 classes; only one method changed

**User performed full Android16 Galaxy S8+ offline validation on ThinkPad:**
\`\`\`text
PASS: original telephony-common.jar SHA-256
  8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1
PASS: unmodified DEX039 roundtrip via baksmali/smali 3.0.10 --api 29
PASS: RAF0 candidate DEX039 assemble/disassemble and SHA1/Adler32
  SHA-256 c1a641b18d92a28dd2c3f25a7930febc91e97d2199fb434e42726360b042a0e4
  6,117,972 bytes
PASS: ALICE_S8P_RAF0_STRICT_DEX_DIFF_V2.py --selftest
PASS: 3628 Smali classes compared; only RIL.makeStaticRadioCapability changed
PASS: original/candidate DEX class, field and prototype counts preserved
REPORT: ~/Downloads/ALICE_ROM_RADIO_DUMP/raf0-offline/ALICE_RAF0_STRICT_DIFF_REPORT.json
NOT FLASHABLE: ART verification, property_contexts and rollback untested
\`\`\`

An earlier strict-diff V1 test failed with a bare \`STOP:\` because it checked *the textual name* of a Smali exception-handler label \`:alice_raf_catch\`, which the assembler is free to canonicalize. In V2, validation correctly checks the actual RuntimeException catch table + move-exception, so the strict diff passed. This was a verifier false negative, not a broken DEX patch.

**Current status:** bytecode construction and same-method-only semantic Smali comparison passed. **Not an installed patch, not proof of ART verification or radio success.** The experimental framework needs correct first-boot ART verification, property_contexts for feature gate \`persist.vendor.alice.s8p_raf0_resource_fallback\` (default OFF), dependable recovery/rollback, and an independent test of system/non-system resource parsing. Attempting to copy a candidate into \`/system/framework/telephony-common.jar\` without those gates is unsafe: bootclasspath and preopt constraints can bootloop or disable telephony.

For offline ZIP metadata testing, a host-only script \`ALICE_S8P_RAF0_OFFLINE_JAR_AUDIT.py\` was supplied to user, requiring exact original SHA, trial DEX SHA, 3628-class PASS report, and reproducing original 787 ZIP entries while preserving all 786 non-DEX entry bytes. It deliberately produces \`.NOT-FOR-INSTALL.zip\`, not a flashable artifact. This script is only selftested on a small ZIP fixture: **no owner's full archive run yet**.

Objective remains repair Android16's hardcoded \`RIL.makeStaticRadioCapability()\` RAF=0 fallback, which in itself does not imply modem can do concurrent 4G+4G. Keep working kernel 4.4.302-Alice-V12R5T and camera/video.


## 2026-10-25 offline trial DEX strict PASS, ZIP flag 0x808 audit bug resolved

Owner's **real ThinkPad** completed Smali roundtrip and strict comparison:
\`\`\`
PASS: offline trial DEX checksum, DEX039 and patch string markers
TRIAL DEX SHA256=c1a641b18d92a28dd2c3f25a7930febc91e97d2199fb434e42726360b042a0e4
DEX bytes=6117972
PASS: patch references survived assemble / disassemble
PASS: 3628 Smali classes compared; only RIL.makeStaticRadioCapability changed
PASS: original/candidate DEX class, field and prototype counts preserved
\`\`\`
The first \`ALICE_S8P_RAF0_OFFLINE_JAR_AUDIT.py\` incorrectly stopped at \`ZIP entry metadata changed: META-INF/MANIFEST.MF\`. Inspection of **exact original uploaded 6,525,408-byte JAR** showed manifest \`flag_bits=0x808\`, where bit 0x8 represents a ZIP data descriptor and bit 0x800 UTF-8. Python \`zipfile.writestr()\` normalizes these flags (e.g., to 0x800), even when the file content is unchanged. This is a **ZIP repackaging audit implementation bug**, not a DEX failure. Do not disable ZIP integrity tests to suppress the report.

A corrected **offline byte-preserving ZIP graft** was implemented and tested locally against the owner's exact original JAR. It replaces only the \`classes.dex\` stored payload, updates its local+central CRC and sizes, shifts subsequent central-directory local-header offsets, and updates the EOCD central-directory offset. It does **not** recompress the other 786 entries, thereby retaining the original 0x808 flags, data descriptors, and local-record bytes. Using the original DEX plus 316 dummy bytes (exact size delta for real trial DEX), it PASSed \`zipfile.testzip()\`, 786 byte-identical untouched local entry ranges and all metadata/flags checks. The corrected user's downloadable script is \`ALICE_S8P_RAF0_OFFLINE_JAR_AUDIT_V2.py\` from the ChatGPT conversation; **the owner has not yet tested it against the actual candidate DEX**.

**Important:** offline ZIP CRC/structure checks do not validate system ART bootclasspath operation, SELinux property visibility/registration or tested recovery. No JAR has been installed on S8+ and **4G+4G remains unproven**. The candidate is explicitly named \`telephony-common.RAF0-TRIAL.NOT-FOR-INSTALL.zip\`. Do not flash.


## 2026-10-25 REAL ThinkPad offline JAR audit V2 PASS (no device changes)

Owner executed \`ALICE_S8P_RAF0_OFFLINE_JAR_AUDIT_V2.py --selftest\` and then the full audit **twice**, obtaining:
\`\`\`text
PASS: offline raw-ZIP graft / preserve-other-local-bytes fixture
PASS: preserved exact compressed/local entry bytes for 786 non-DEX members
PASS: original ZIP flag_bits and metadata preserved; ZIP CRC verifies
PASS: SHA-pinned trial DEX and strict 3628-class structural diff
AUDIT REPORT: /home/halo-pmf/Downloads/ALICE_ROM_RADIO_DUMP/raf0-offline/ALICE_JAR_OFFLINE_AUDIT_V2.json
CANDIDATE (DO NOT FLASH): /home/halo-pmf/Downloads/ALICE_ROM_RADIO_DUMP/raf0-offline/telephony-common.RAF0-TRIAL.NOT-FOR-INSTALL.zip
NOT ART VALIDATED, NOT READY FOR INSTALL OR FLASH
\`\`\`
The earlier \`STOP: ZIP entry metadata changed: META-INF/MANIFEST.MF\` was from V1; **V2 resolved it** by byte-preserving local ZIP records including original \`0x808\` flags. The owner confirmed the fixed algorithm works on the actual trial DEX, not only on a test fixture.

**Verified stages completed on ThinkPad:** exact original JAR SHA256, DEX039 smali roundtrip, patched DEX SHA256 and integrity, read-back of patched RIL method, source-level 3628-class strict diff (only \`RIL.makeStaticRadioCapability\` changed), 787-member ZIP preserve-audit (786 non-DEX entries unchanged). These validations are independent of ART class loading; do NOT label the \`.zip\` flash-ready.

**Critical gating concerns before any installation:** candidate only enables its RAF fallback if \`ro.product.vendor.device=dream2lte\` AND \`persist.vendor.alice.s8p_raf0_resource_fallback=true\`, which defaults FALSE. A vendor property requires registered property contexts and appropriate SELinux access; setting a property on an unpatched ROM does nothing. Replacing \`/system/framework/telephony-common.jar\` changes Android BOOTCLASSPATH and may bootloop, regardless of DEX checksum/ZIP CRC PASS. ART verification, ROM signing/cached dexopt and a tested offline rollback/recovery remain UNVERIFIED. A non-flash read-only preflight was added as \`tools/android16/alice_raf0_device_preflight_readonly.sh\` to capture original on-device framework hash, bootclasspath presence, version, SELinux and property contexts; it must not alter data/SIM/camera/root/CP/EFS.

Dual LTE still UNPROVEN; both phones assigned resource-derived RAF=64508 may still result in equal max/min RAF and the same ProxyController no-op, even if the fallback patch can prevent the \`unknown RAF 0\` early return. Do not promise dual 4G.


## 2026-10-25 real device read-only preflight: pre-installation NO-GO

Owner executed \`bash alice_raf0_device_preflight_readonly.sh\` on ThinkPad X270 against connected **physical** S8+; complete with \`READ ONLY, NO DEVICE CHANGES\`.
\`\`\`text
ADB: device
ro.product.vendor.device=dream2lte
ro.product.device=r0s
ro.build.display.id=BP2A.250605.031.A3.S901BXXSNGZD7
ro.build.version.release=16
ro.boot.verifiedbootstate=green
uname -r=4.4.302-Alice-V12R5T-MGLRU-KSU32590-Enf+
/system/framework/telephony-common.jar 6525408 bytes
on-device JAR SHA256=8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1
host original JAR SHA256 matches exactly
BOOTCLASSPATH includes /system/framework/telephony-common.jar
SELinux=Enforcing
persist.vendor.alice.s8p_raf0_resource_fallback= [UNSET]
SDK=36
dalvik.vm.usejit=true
\`\`\`

\`property_contexts\` scan found generic \`persist.vendor.\` mapping to \`vendor_default_prop\` in Android system and numerous other prefixed mappings, but **no exact registered \`persist.vendor.alice.s8p_raf0_resource_fallback\` rule was demonstrated**. Generic mapping is NOT proof Telephony has read/write permissions in SELinux enforcing mode; and an absent property means the trial's \`SystemProperties.getBoolean(..., false)\` returns **false**, leaving old zero-RAF fallback even IF the patched DEX were installed.

Status gates:
- PASS: source checksum, structural diff of 3628 Smali classes, reconstructed patched DEX checksum, original non-DEX archive data preservation, on-device original framework hash.
- FAIL/NOT VERIFIED: ART runtime verification of patched BOOTCLASSPATH code, rollout and tested full offline recovery from nonboot, SELinux property-context registration and accessibility, real modem GET_RADIO_CAPABILITY restoration, LTE on MobiFone, dual 4G simultaneously.
- **NO-GO for installing candidate, KernelSU early-boot mount, direct overwrite of /system/framework, fastboot/Heimdall flash, or setting persistent vendor properties on this production phone.** Preserve working boot V12R5T, vendor, camera/video, Viettel LTE baseline.

The original trial targets \`RIL.makeStaticRadioCapability()\` exactly. Even if RAF0 fallback becomes nonzero when explicitly enabled, both slots could receive the **same** parsed RAF, leaving \`ProxyController.getMaxRafSupported()==getMinRafSupported()\` and therefore no actual hardware RF handoff; the owner's Xiaomi-like simultaneous LTE goal is still speculative and NOT solved. Do not call it a dual 4G ROM fix.

For deployment planning, require a ROM-integrated compatible framework build plus correct SELinux property policy (or a reviewed, safe alternative gating scheme), a user-tested independent custom recovery path with on-device restoration of original JAR/system partition, and device-side ART boot safety tests before exposing any flashable build. Merely reading \`ro.boot.verifiedbootstate=green\` does not prove any of these.
