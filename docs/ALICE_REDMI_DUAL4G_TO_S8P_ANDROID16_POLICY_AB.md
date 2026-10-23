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

## Host safety constraints

For S8+ Exynos 8895, 4G+4G requires two independently observed LTE PS registrations at the same time; neither two HIDL IRadio names nor `9,9` satisfies this criterion. Never use Redmi Qualcomm firmware/binaries on Samsung. Do not overwrite Test7 proprietary RIL ELF, Samsung modem firmware, CP, EFS or IMS profiles without verified rollback and hardware evidence.
