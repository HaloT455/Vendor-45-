# Galaxy S8+ SM-G955F/FD — SIM2 LTE role handoff study (23 Oct 2026)

**User's confirmed reference:** Their supplied original boot.img + vendor.new.dat.br allows SIM1 LTE (4G), SIM2 UMTS/HSPA (3G). This is a functioning **4G+3G reference**, not evidence that both can maintain LTE simultaneously.

## Research conclusion

Samsung's Exynos 8895 S8/S8+ dual-SIM (G955FD) was designed/observed with **one LTE-active SIM at a time**. A Samsung Members technical response (2018) explicitly states changing LTE selection to one SIM moves the other to a lower network. XDA user reports for G955FD also confirm 4G+3G, not two concurrent 4G registrations:

- https://r2.community.samsung.com/t5/Galaxy-S/How-can-i-get-those-sim-4G-network/m-p/160777/highlight/true
- https://xdaforums.com/t/s8-dual-sim-is-it-4g-3g-or-4g-2g-dual-standby.3584061/
- Samsung Exynos 8895 official page describes one gigabit LTE modem, not a dual-independent-LTE configuration: https://semiconductor.samsung.com/processor/mobile-processor/exynos-9-series-8895/

**Hard distinction:** Setting `ro.telephony.default_network=9,9`, `preferred_network_mode=9,9`, two IRadio HIDL instances or two LTE-permitted subscription masks does NOT make two LTE RF stacks active at once. Fake RAF values do not supply hardware capabilities and can break telephony. This branch does **not** alter modem firmware, EFS, NV, IMEI, CP, radio drivers, kernel boot image, Camera HAL or Video6.

## Feasible software target

**Switch which SIM is allowed to use LTE**: when mobile data selection changes to SIM2, SIM2 should have the opportunity to register LTE and SIM1 may drop to 3G. If SIM2 remains 3G, first establish that Android 16 actually changed default-data PhoneId; then isolate whether `PhoneSwitcher`, `RadioConfig.setPreferredDataModem`, `setDataAllowed`, cached modem RadioCapability / RAF 0, policy masks or CP stack ownership prevented a handoff.

AOSP implementation:
- https://android.googlesource.com/platform/frameworks/opt/telephony/+/71f0a1f4f2c0845a896964564b723e42321bbb02/src/java/com/android/internal/telephony/data/PhoneSwitcher.java
- https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/main/radio/config/1.1/types.hal

Past branch `work/a16-dsds-lte-runtime-handoff` records eight historical `setPreferredNetworkType: Abort, unknown RAF: 0` events from 2026-10-20, and a working LTE framework overlay, but did NOT capture a contemporaneous SIM-specific modem return. These historical events do not establish that RAF 0 is still happening now or that the old known-working reference also suffers it.

## No-flash two-state check (Linux + connected S8+)

The following probe is **read-only** and only saves a privacy-filtered JSON, not raw telephony logs or subscriber identifiers.

```bash
curl -fLsS "https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-sim2-lte-handoff-audit-20261023/tools/alice_sim2_lte_handoff_probe.py" -o ~/ALICE_SIM2_LTE.py
python3 ~/ALICE_SIM2_LTE.py --selftest
```

In Android Settings > Connections > SIM manager, leave both SIMs enabled, set Mobile data to **SIM1**, confirm it reaches LTE, then run:

```bash
python3 ~/ALICE_SIM2_LTE.py --snapshot sim1 --output ~/SIM1_LTE.json
```

Manually set **Mobile data = SIM2**, wait for network to settle, keep preferred network `LTE/3G/2G auto`, then:

```bash
python3 ~/ALICE_SIM2_LTE.py --snapshot sim2 --output ~/SIM2_LTE.json
python3 ~/ALICE_SIM2_LTE.py --compare ~/SIM1_LTE.json ~/SIM2_LTE.json
```

Interpret:
- `LTE_ROLE_HANDOFF_REPORTED`: getprop RAT suggests SIM2 became LTE after switching. Verify separate WWAN registration, a call, SMS and mobile data before claiming verified LTE.
- `SIM2_LTE_HANDOFF_NOT_OBSERVED`: actual default-data phone switched to SIM2 but its reported RAT remains 3G. Test SIM2 alone (SIM1 actually absent) next, and inspect live RadioCapability callback and CP handoff.
- `DATA_SWITCH_NOT_CONFIRMED`: do not diagnose radio before confirming defaultDataPhoneId changed 0 -> 1.
- `NOT_ENOUGH_BASELINE_EVIDENCE`: first confirm SIM1 LTE with known working firmware.

`gsm.network.type` and `dumpsys isub` are ROM-dependent; unknown, absent, or stale fields are **inconclusive**. Historical filtered radio log counters are diagnostic only and do not prove a current error.

## Decision and release gates

If SIM2 does not reach LTE **even with SIM1 physically removed**, distinguish provisioning/coverage, SIM hardware, network mode, modem CP and Android framework bugs. If SIM2 reaches LTE alone but not when SIM1 is present, focus on DSDS LTE owner transition. Only patch the identified component after the controlled results; DO NOT transplant proprietary RIL binaries, invent modem RAF, modify EFS/IMEI, or flash old ramdisk with new R16 EnergyStep.

No boot/vendor modification is made in this investigation branch. The owner's working camera/video and both SIM functions remain protected. Green GitHub CI checks only code and byte preservation, **not any device's ability to use two LTE SIMs**.

## 2026-10-23: Simultaneous LTE candidate gate (no fake 4G modem patch)

Official Samsung Members 2018 response for Galaxy S8 dual-SIM states choosing 4G on one slot switches the other to a lower network:
https://r2.community.samsung.com/t5/Galaxy-S/How-can-i-get-those-sim-4G-network/m-p/160771/highlight/true

Exynos 8895 specifications confirm a single integrated LTE Cat.16 modem, but do not advertise two independent concurrent LTE registrations:
https://semiconductor.samsung.com/processor/mobile-processor/exynos-9-series-8895/

AOSP `cmd phone set-allowed-network-types-for-users` only sets the **USER** allowed-RAT mask; it cannot create another LTE baseband/RF stack. The existing vendor already sets `ro.telephony.default_network=9,9`, and both user LTE policies were previously observed allowed. An extra property or setting is not a justified dual-4G modification.

Run `python3 tools/alice_sim2_lte_handoff_probe.py --dualcheck` with two SIMs inserted. This evaluates both current RAT indicators **without changing anything**, marks only `BOTH_LTE_RAT_REPORTED_NEEDS_WWAN_CONFIRMATION` when both SIMs report LTE, and expressly refuses to treat properties alone as two LTE registrations. True proof requires contemporaneous `WWAN PS HOME LTE` registration from both phone IDs, verified separately and without exposing subscriber data.

No flash-ready boot/vendor `4G+4G` mod can be justified from the available hardware documentation, proprietary modem evidence or real-device logs. The only testable software goal remains LTE-owner handoff to SIM2 (with SIM1 falling back), dependent on current Android16 RIL/RadioConfig behavior. Do not disturb CP/EFS/NV/IMEI or the user-verified camera vendor.
