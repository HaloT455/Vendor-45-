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

## Host safety constraints

For S8+ Exynos 8895, 4G+4G requires two independently observed LTE PS registrations at the same time; neither two HIDL IRadio names nor `9,9` satisfies this criterion. Never use Redmi Qualcomm firmware/binaries on Samsung. Do not overwrite Test7 proprietary RIL ELF, Samsung modem firmware, CP, EFS or IMS profiles without verified rollback and hardware evidence.
