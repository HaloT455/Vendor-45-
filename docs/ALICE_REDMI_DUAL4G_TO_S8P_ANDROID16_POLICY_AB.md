# Redmi Note 5 Pro Dual 4G → Exynos8895 Android16 compatibility A/B

**Goal:** restore Viettel SIM1 LTE registration while leaving the owner's MobiFone SIM2 installed and active, then test LTE-owner handoff to SIM2. No user-side SIM removal required for this A/B.

## What the Xiaomi precedent establishes (and does not)

Xiaomi Redmi Note 5 Pro (Qualcomm Snapdragon 636) received a MIUI 9.5 Android 8.1 update advertising Dual 4G VoLTE in June 2018. Reports were mixed: some observed dual 4G, while others could not use dual VoLTE in their tests. Sources: https://www.fonearena.com/blog/253594/xiaomi-redmi-note-5-pro-android-oreo-dual-4g-volte-india-download.html and https://telecomtalk.info/android-oreo-redmi-note-5-pro/175884/ .

**Cannot copy:** Qualcomm modem binary/firmware, IMS carrier profile, PHY/RF clock routing, proprietary modem hooks, and dual-attach bitmasks are specific to Snapdragon and not interchangeable with Samsung Exynos8895/SS310AP.

**Portable lesson:** Android per-subscription preferred RAT masks, a correct LTE-capable phone policy, and actual RadioConfig/RadioCapability ownership handoff matter independently of a generic build.prop default. AOSP Android16 Telephony uses USER/CARRIER/POWER allowed network types in an intersection; stock default network mode `9,9` is **not proof** that the effective user restriction still includes LTE. See https://developer.android.com/reference/android/telephony/TelephonyManager and https://android.googlesource.com/platform/packages/services/Telephony/+/refs/heads/main/src/com/android/phone/TelephonyShellCommand.java .

## Evidence from user's SM-G955F

Owner's most recent V12R5T Android16 ADB output:
- `gsm.sim.state=LOADED,LOADED`; `persist.radio.multisim.config=dsds`;
- `gsm.network.type=UMTS,UMTS`; `ro.telephony.default_network=9,9`;
- `gsm.operator.alpha=,MobiFone`;
- slot0 Viettel `mVoiceRegState=OUT_OF_SERVICE`, `mDataRegState=OUT_OF_SERVICE`;
- slot1 MobiFone `mVoiceRegState=IN_SERVICE`, `mDataRegState=OUT_OF_SERVICE`;
- `ril-daemon=running` and two radio HAL slots are present; no basis to create a second rild process;
- no verified runtime proof of dual LTE hardware.

## Actual safe A/B implementation

Added `tools/alice_lte_slot1_policy_trial.py` which:
1. Read-only default: show actual slot0 and slot1 USER allowed-RAT masks, current RAT, and slot0 registration; does not expose subscriber identifiers.
2. On explicit `--apply-slot1`: require dream2lte+DSDS+SIM1 ready, read slot 0 USER mask from Android `cmd phone get-allowed-network-types-for-users -s 0`. AOSP's bit 13 (8192) permits LTE. If already enabled, **do not write anything**; recommend RIL/CP registration triage.
3. If absent, save the original USER mask locally (`ALICE_S8P_SIM1_LTE_POLICY_BACKUP.json`, mode 0600), set original mask OR LTE bit for slot 0 only, preserving all non-LTE bits. Do not change carrier/power policy, preferred default data SIM, airplane mode, SIM2 RAT mask, EFS/CP/NV/IMEI.
4. Verify readback; wait for **LTE RAT AND data IN_SERVICE**. On failure/timeout, try restoring the original mask. If ADB drops, backup remains and `--rollback` is available. A provisional success also retains backup for manual rollback.
5. Offline selftest is wired to `.github/workflows/alice-a16-samsung-video6-fix.yml`. CI cannot verify modem registration.

## Commands on Linux with both SIMs physically installed

```bash
curl -fL https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-sim2-lte-ab-20261023/tools/alice_lte_slot1_policy_trial.py -o alice_lte_slot1_policy_trial.py
python3 alice_lte_slot1_policy_trial.py --selftest
python3 alice_lte_slot1_policy_trial.py
# Only if slot0_lte_allowed is false and the read-only command succeeds:
python3 alice_lte_slot1_policy_trial.py --apply-slot1
# At any time:
python3 alice_lte_slot1_policy_trial.py --rollback
```

If the script reports `slot0_lte_allowed: true` then LTE is already enabled at USER level, and **no patch to build.prop/early init/switching masks can fix the SIM1 registration alone**. Next step is masked-slot Telephony allowed-type intersections, RIL RadioCapability callbacks, network attach reasons, and baseband CP LTE allocation; not firmware flashing nor any claim of 4G+4G.

## User V12R5T runtime result and fixed parser (2026-10-24)

The actual device printed:

`GPRS|EDGE|UMTS|HSDPA|HSUPA|HSPA|LTE|HSPA+|GSM|LTE_CA`

for `cmd phone get-allowed-network-types-for-users -s 0`. This **explicitly includes LTE** in USER policy. Older A/B tester incorrectly expected a raw binary output and mistakenly used `1 << 13` for LTE, while Android TelephonyManager's `NETWORK_TYPE_BITMASK_LTE` equals `4096 = 1 << 12`. The old selftest fixture incorrectly asserted a bit in a synthetic binary mask. **Both are testing-tool bugs, not evidence of phone or Vendor firmware errors.**

Fixed `tools/alice_lte_slot1_policy_trial.py`: parses AOSP symbolic RAT output into the correct `1 << (network_type - 1)` bitmask; also supports binary output; rejects unknown names and stops without writing; corrected LTE bit to 4096; selftest uses the owner's actual symbolic string. The A/B now reports `NO_POLICY_FIX_NEEDED` instead of modifying USER policy when LTE is already enabled. Official AOSP GET prints a symbolic mask, SET expects binary: https://android.googlesource.com/platform/packages/services/Telephony/+/refs/heads/main/src/com/android/phone/TelephonyShellCommand.java .

**NEXT PROBLEM IS NOT USER RAT POLICY:** Viettel SIM1 remains `mVoiceRegState=1(OUT_OF_SERVICE),mDataRegState=1(OUT_OF_SERVICE)`; MobiFone SIM2 shows voice IN_SERVICE, data OUT_OF_SERVICE. `gsm.network.type=UMTS,UMTS`, `gsm.operator.alpha=,MobiFone`. Both physical SIMs can stay installed. Gather slot mapping and sanitized radio reject/RadioCapability events before changing modem or system image. Do not repeatedly reset `ro.telephony.default_network=9,9`.

## Redmi Note 5 Pro (whyred) REAL rollout / compatibility evidence

- Snapdragon 636 was initially shipped with only one 4G-ready slot for users in some configurations. The India Android 8.1 MIUI 9.5.14.0.OEIMIFA rollout (June 26 2018) explicitly included **Dual 4G optimization**. Prior 9.5.11 offered a Dual 4G VoLTE switch but FoneArena testers found inconsistent actual simultaneous registrations. [Release report](https://www.fonearena.com/blog/253594/xiaomi-redmi-note-5-pro-android-oreo-dual-4g-volte-india-download.html)
- A 2019 OxygenOS 9.0.2 port to the same Snapdragon 636 **did** register Jio and Airtel VoLTE concurrently in a hands-on test, but the port had occasional call drops and SIM detection failure. [Independent hands-on test](https://www.fonearena.com/blog/273515/xiaomi-redmi-note-5-pro-android-pie-oxygenos-9-0-port.html). This establishes capability **on Qualcomm Snapdragon 636**, not Exynos8895.
- A Qualcomm modem image, IMS carrier configuration or QMI/RIL backend **cannot** be transplanted onto Samsung's SS310AP. Android framework masks and RadioCapability checks are *conceptual* lessons; modem hardware/vendor support is essential.
- A newer public whyred custom ROM device tree exists ([example](https://github.com/Atom-X-Devs/android_device_xiaomi_whyred)), but searching its properties.mk and framework overlay did **not** identify a standalone, portable Dual 4G toggle/patch. Do not invent one.

## Subsequent live S8+ owner status on 2026-10-24

The owner later reported Viettel SIM1 LTE working with both SIMs inserted. Subsequent `gsm.network.type=LTE,IWLAN`, `gsm.operator.alpha=Viettel,`; `defaultDataSubId=1` with **unknown subscription→slot mapping**. Now owner reports MobiFone SIM2 has regained carrier/network visibility. **Do not equate SIM2 MobiFone registration with SIM2 LTE**, and do not assume `IWLAN` is 3G. Preserve the working boot/vendor, camera and SIM1 LTE; no modem/CP/EFS writes or blind RadioCapability firmware patch.

The earlier `GET_RADIO_CAPABILITY` invalid native RIL response and RAF=0 fallback remain important compatibility defects, but later **SIM1 LTE working shows that RAF=0 is not in itself sufficient evidence of a permanent blocker to all LTE service.** We need a simultaneous snapshot of PS/CS WWAN registration for *both* phones before claiming dual LTE or selecting repair target.

**Next verification, both SIMs left inserted:**

```bash
adb -d shell 'getprop gsm.sim.state; getprop gsm.operator.alpha; getprop gsm.network.type; dumpsys isub | grep defaultDataSubId'
adb -d shell dumpsys telephony.registry | grep 'mServiceState='
```

Confirm two independent LTE access technologies from WWAN PS registration and both PS IN_SERVICE in one near-simultaneous capture before claiming true 4G+4G. When only one phone has LTE and the other UMTS or IWLAN, test data-SIM switch (keeping both SIMs installed) to distinguish single LTE owner handoff vs simultaneous LTE attach. A data-subscription switch may drop LTE on SIM1 and temporarily disrupt calls/data; never claim 4G+4G based on two Android allowed-RAT masks.

## Definitive current owner's registration snapshot — 2026-10-24

**Galaxy S8+ dream2lte Exynos8895, both SIMs physically installed, Android 16/V12R5T:** the user captured `dumpsys telephony.registry` and parsed `NetworkRegistrationInfo`, showing:

| Domain | Viettel SIM1 | MobiFone SIM2 |
| --- | --- | --- |
| CS WWAN (mobile voice/circuit service) | HOME, RAT=LTE | HOME, RAT=UMTS |
| PS WWAN (cellular packet data) | HOME, RAT=LTE | NOT_REG_OR_SEARCHING, RAT=UMTS |
| PS WLAN (IWLAN transport) | UNKNOWN, IWLAN | HOME, IWLAN |
| SIM state | LOADED | LOADED |

Both registered operators appeared in `gsm.operator.alpha=Viettel,MobiFone`. **This definitively shows LTE+UMTS, not simultaneous LTE+LTE.** MobiFone's `HOME` on PS WLAN/IWLAN does NOT count as LTE radio registration on PS WWAN. MobiFone can make normal CS voice calls on UMTS; mobile PS registration is currently missing.

**Relevant historical manufacturer evidence:** Samsung's Galaxy S8/S8+ launch specifies `4G + 3G Hybrid Slot for Dual SIM` ([Samsung Singapore](https://www.samsung.com/sg/news/local/samsung-announces-availability-of-galaxy-s8-s8plus-and-galaxy-tab-s3-in-singapore/)); Samsung community support said the other slot is automatically downgraded when LTE is selected on one slot ([Samsung Members](https://r2.community.samsung.com/t5/Galaxy-S/How-can-i-get-those-sim-4G-network/m-p/160777/highlight/true)). This is supporting evidence for a **device/modem limitation**, not an independently verified modem datasheet proving dual LTE physically impossible in every CP build.

**Safest discriminating A/B, no flash, both SIMs installed:**
1. Save this initial snapshot `LTE,UMTS`. Leave Viettel LTE working.
2. Through Settings > Connections > SIM manager, set the *mobile-data SIM* to MobiFone SIM2; expect momentary data interruption.
3. Read *both* `CS WWAN` and `PS WWAN` RATs and registration states again.
4. If `UMTS,LTE` with SIM2 PS WWAN HOME, LTE owner handoff is possible but simultaneous dual LTE remains unproven. Restore Viettel data SIM if preferred.
5. If `LTE,UMTS` while MobiFone is the confirmed default data slot, radio-stack handoff or policy could be defective; gather `setPreferredDataModem` and RadioConfig/RAF log events before changing any HAL.
6. If `UMTS,UMTS`, both lost LTE ownership: restore Viettel and inspect SIM2 LTE attach. **No automatic CP/EFS writes, no Qualcomm modem transplant, and no blanket 4G+4G claim.**

`mMaxActiveDataSubscriptions=2` in PhoneCapability and allowing LTE for both slots in USER policy are framework state, neither is proof of simultaneous independent LTE registration.

## 2026-10-24: Verified Xiaomi release vs S8+ actual modem limits

**Verified whyred ROM:** official Xiaomi `V9.5.14.0.OEIMIFA` (June 2018, Android 8.1) lists `Optimized Dual 4G` in the changelog. Official firmware-tracker evidence: https://xmfirmwareupdater.com/miui/whyred/stable/V9.5.14.0.OEIMIFA/ . This confirms a firmware feature delivered on Qualcomm Snapdragon 636, but the proprietary patchset/changed modem NV/RF mechanisms are NOT disclosed by the changelog. Therefore do **not** invent a small transferable `build.prop` change or assert what baseband source Xiaomi patched.

**Samsung manufacturer documented original design:** `Galaxy S8/S8+ (4G + 3G Hybrid Slot for Dual SIM)` in Samsung's official launch specifications: https://www.samsung.com/sg/news/local/samsung-announces-availability-of-galaxy-s8-s8plus-and-galaxy-tab-s3-in-singapore/ . This supports a strong **hardware/modem-or-product-policy limit** hypothesis. It is not proof that no hypothetical new CP firmware could ever support a second LTE standby path, but no validated Exynos8895 Dual LTE firmware is available here.

**Current user's fixed evidence:**
- slot0/Viettel `subId=1`, PS WWAN HOME LTE; voice HOME LTE.
- slot1/MobiFone `subId=2`, CS WWAN HOME UMTS; PS WWAN NOT_REG_OR_SEARCHING UMTS; WLAN IWLAN is not LTE on cellular RF.
- `defaultDataSubId=1`, `activeDataSubId=1` continue to point to Viettel; the user has **not produced an actual SIM2 DDS selection event**. `PhoneSwitcherForMultiSim` reports `mPreferredDataPhoneId=0,mPrimaryDataSubId=1,ddsSubId=1`.
- Both `cmd phone get-allowed-network-types-for-users -s 0/1` contain LTE; `ro.telephony.default_network=9,9`; both physical SIMs loaded. **User masks and default props are already correct.**
- Both native Samsung RIL slots previously logged `responseRadioCapability: Invalid response` and a static fallback `RAF=0`. Phone1 still logged `setPreferredNetworkType: Abort, unknown RAF: 0`. Live `cmd overlay lookup --user 0 android android:string/config_radio_access_family` is `GSM|CDMA|EVDO|WCDMA|LTE`: this is valid and does not justify replacing RRO blindly.

**Android16 source call graph for a true user data SIM switch:** `SubscriptionManagerService.setDefaultDataSubId(2)` checks `MODIFY_PHONE_STATE`, updates `mDefaultDataSubId`, calls `remapRafIfApplicable()`, and notifies the MultiSim controller and PhoneSwitcher. Ref: https://android.googlesource.com/platform/frameworks/opt/telephony/+/android16-release/src/java/com/android/internal/telephony/subscription/SubscriptionManagerService.java . Opening Settings by ADB or writing global settings is NOT equivalent. Do **not** execute a guessed `service call isub N 2` where transaction IDs are version-dependent.

**Working repair stages, strict gates:**
1. Preserve working V12R5T boot, camera, original paired vendor, and dual voice service.
2. Confirm one **actual** default/active DDS change from 1 to 2, then capture both WWAN PS/CS RATs and radio logs. If MobiFone LTE and Viettel UMTS, that proves LTE handoff but not 4G+4G.
3. Independently investigate Samsung native RIL malformed `GET_RADIO_CAPABILITY` callback versus expected Android16 HIDL/legacy RIL payload size; use ABI evidence, not a fabricated RadioCapability mask. Fixing RAF0 may restore clean allowed-RAT updates but **does not guarantee two LTE stacks**.
4. Never force LTE on both with a blind Phone.java framework bypass, modify modem CP/EFS/NV, or transplant Qualcomm `NON-HLOS.bin` into Exynos8895.
5. Claim Dual 4G success only when **simultaneous** WWAN PS registrations on BOTH phone IDs are HOME/ROAMING LTE and calls/data are tested. Until then the proven state is LTE+UMTS.

## Host safety constraints

For S8+ Exynos 8895, 4G+4G requires two independently observed LTE PS registrations at the same time; neither two HIDL IRadio names nor `9,9` satisfies this criterion. Never use Redmi Qualcomm firmware/binaries on Samsung. Do not overwrite Test7 proprietary RIL ELF, Samsung modem firmware, CP, EFS or IMS profiles without verified rollback and hardware evidence.


## Runtime proof: revised SIM handoff probe passes on real Galaxy S8+ (2026-10-24)

Owner ran \`tools/alice_sim2_lte_handoff_probe.py\` from commit \`f04c5f04991a\`. \`--selftest\` output PASS; \`--snapshot sim1\` confirmed:
- \`ro.product.vendor.device=dream2lte\` and \`persist.radio.multisim.config=dsds\`;
- mapping physical \`slot0→subId1\` Viettel, \`slot1→subId2\` MobiFone;
- \`default_data_sub_id=1\`, \`active_data_sub_id=1\`, \`default_data_phone_id_verified=0\`;
- phone0 \`CS WWAN HOME LTE\`, \`PS WWAN HOME LTE\`, \`ps_lte_registered=true\`;
- phone1 \`CS WWAN HOME UMTS\`, \`PS WWAN NOT_REG_OR_SEARCHING UMTS\`, \`ps_lte_registered=false\`;
- legacy getprop indicators \`LTE,IWLAN\`, demonstrating why getprop alone is misleading;
- recent 350-line radio buffer error counts all zero. **This DOES NOT prove older RAF0 errors are resolved**, since these are counts over a rolling short log window;
- \`wwan_ps_both_lte_registered=false\`.

This is the **validated stable baseline**. No flash or modem edit was made; the diagnostic code does not repair LTE. It positively verifies the data handoff A/B **has not happened yet**: MobiFone is NOT the default data subscription. Any follow-up probe should save \`--snapshot sim1 --output sim1.json\` before selecting MobiFone, then \`--snapshot sim2 --output sim2.json\` once \`defaultDataSubId=2\` and compare. Labels alone do not prove data switching. Avoid modifying EFS/CP or guessing binder transaction IDs; Android16 \`cmd phone\` does not provide a generic set-default-data-sub-ID verb in AOSP; supported Settings/privileged Telephony API is required.



## Verified real device switch to MobiFone and failed PS LTE handoff (2026-10-24)

**Major breakthrough:** Owner compiled \`tools/android16/AliceDataSimSwitch.java\` into a 3136-byte dex jar using Google's R8 on ThinkPad; \`status\` successfully queried live ISub. Then ran \`set 2\` as KernelSU root:
\`\`\`text
ALICE_DATA_SIM: Viettel subId=1 phoneId=0; MobiFone subId=2 phoneId=1; defaultDataSubId=1
ALICE_DATA_SIM_REQUEST: 1 -> 2
ALICE_DATA_SIM_READBACK: 2
ALICE_DATA_SIM_DDS_APPLIED: radio/network registration not yet verified

adb shell dumpsys isub:
defaultDataSubId=2
activeDataSubId=2

alice_sim2_lte_handoff_probe.py --compare sim1.json sim2-after-handoff.json:
status=SIM2_LTE_HANDOFF_NOT_OBSERVED
default_data_phone_id_before=0
default_data_phone_id_after=1
sim1_wwan_ps_lte_before=true
sim1_wwan_ps_lte_after=false
sim2_wwan_ps_lte_after=false
active_data_sub_matches_slot1=true
simultaneous_dual_lte_proven=false
\`\`\`

**Updated diagnosis:** Prior \`DATA_SWITCH_NOT_CONFIRMED\` hypothesis is now RESOLVED: real AOSP Android16 ISub \`setDefaultDataSubId(2)\` invocation was accepted and the new default AND active data-subscription changed. Therefore do not ask user to repeat the same UI step or write the same setting again. The unresolved fault is **LTE/packet-switched registration after DDS handoff to phoneId1**. Note \`PS LTE false\` can mean PS registration on UMTS, or no PS cellular registration; it does NOT by itself prove total MobiFone data outage or support/non-support of specific LTE RF bands. Need inspect two **actual** PS WWAN registration and RAT values from \`sim2-after-handoff.json\` and relevant \`ProxyController\` / \`RILJ\` / \`RILC\` logs, preferably captured immediately after handoff.

AOSP Android16 \`SubscriptionManagerService.setDefaultDataSubId\` calls \`remapRafIfApplicable\`, in which \`ProxyController.getMaxRafSupported()\` is assigned to the target data slot and the minimum to the other via \`ProxyController.setRadioCapability(rafs)\`. This is a key path for devices with dynamic LTE capability assignment. AOSP: https://android.googlesource.com/platform/frameworks/opt/telephony/+/android16-release/src/java/com/android/internal/telephony/subscription/SubscriptionManagerService.java

Prior logs showed \`responseRadioCapability: Invalid response\` for legacy Samsung RIL; AOSP libril checks \`response == NULL || responseLen != sizeof(RIL_RadioCapability)\`: https://android.googlesource.com/platform/hardware/ril/+/refs/heads/android14-s2-release/libril/ril_service.cpp. It is plausible the RAF transaction fails, but **no post-handoff radio log was yet supplied** to establish causality in this observed handoff. The effective framework \`config_radio_access_family\` had valid \`GSM|CDMA|EVDO|WCDMA|LTE\`, so duplicate overlay work is not warranted.

Added \`tools/alice_dds_lte_post_switch_triage.py\`, offline/read-only, to distinguish cellular PS WWAN UMTS HOME vs PS NOT_REG/SEARCHING vs LTE HOME after a confirmed DDS switch, using the owner's sanitized existing JSON. \`--selftest\` added to Vendor and paired Kernel CI; passing CI or Python fixtures cannot substitute for registering both radio stacks.

**Owner's next read-only steps, while MobiFone selected:**
\`\`\`bash
python3 "$HOME/Downloads/ALICE_DDS/tools/alice_dds_lte_post_switch_triage.py" --before "$HOME/Downloads/sim1.json" --after "$HOME/Downloads/sim2-after-handoff.json"
adb -d shell 'logcat -b radio -b main -d -t 8000' |
  grep -iE 'ProxyController|PhoneSwitcherForMultiSim|responseRadioCapability|setRadioCapability|unknown RAF|GET_RADIO_CAPABILITY|setPreferredNetworkType|RADIO_NOT_AVAILABLE|REQUEST_NOT_SUPPORTED' | tail -90
\`\`\`

**If mobile Internet is broken**, restore known-good \`subId=1\` with the already-built helper, then verify \`defaultDataSubId=1,activeDataSubId=1\` and Viettel WWAN PS LTE; no reboot, CP/EFS write or flash is warranted.

Do not claim Xiaomi-style concurrent 4G+4G solved: no device-level evidence. Keep camera/video and V12R5T.
