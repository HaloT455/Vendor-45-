# ALICE S8+ Android16 SIM2 LTE A/B candidate — 2026-10-23

**STATUS: CI source trial; not phone-tested; not a simultaneous 4G+4G unlock. Do not blind-flash.**

## Why this branch exists
The owner supplied `boot.img` and `vendor.new.dat.br` that **work with SIM1 LTE and SIM2 3G**. Separately they confirmed working Samsung Camera + Video6 on the camera gate image. Earlier Android16 logs showed historical `unknown RAF: 0` aborts, but there is **no evidence** that both LTE stacks can attach simultaneously. S8/S8+ dual SIM is historically 4G+3G; a second LTE profile in `ro.telephony.default_network=9,9` is a **policy allowance**, not a second modem/RF path.

## Isolated vendor correction
Start from `work/a16-r16-paired-sim-camera-20261023`.
Restore `vendor/etc/init/init.vendor.rilcommon.rc` byte-for-byte to the already known camera-capable branch `work/a16-camera-fast-metadata-face-iris-audit`, so `exec_start network_config` is preserved but the original **late** `setprop ro.telephony.default_network ${ro.vendor.radio.default_network}` is not executed.
Early `ro.telephony.default_network=9,9` in `vendor/build.prop` is unchanged; Android16 treats `ro.*` as immutable once set. This removes a possible one-slot override, **not evidence of a second simultaneous LTE link**.

Do not alter modem CP/EFS/NV/IMEI, binary RIL/HIDL/SehRadio, the Camera bridge or Video6 six-int tuple metadata. Unlike the owner-reference init, this branch's init.rc is intentionally modified; other radio configs still match the reference, and the proprietary ELF sizes remain unchanged. No security bypass.

## Pairing
Kernel source: `HaloT455/dream2lte-45` branch `agent/v12r69-r16-sim2-lte-ab-20261023`. It contains the preserved SS310AP/SIPC/SHMEM modem driver and blocks repacking incompatible old HMP/DH2 ramdisk with EnergyStep. **No kernel modem driver patch claims two LTE stacks.**

GitHub Actions workflow: `.github/workflows/alice-a16-samsung-video6-fix.yml` on this branch.
Proposed artifact: `ALICE-S8P-A16-SIM2-LTE-RIL-AB-VIDEO6-UNTESTED-NO-FLASH`.
Expected image: `vendor-a16-sim2-lte-ril-ab-video6-UNTESTED.img`.
The kernel workflow exports Image/dtb and contracts, not an on-device-verified `boot.img`. Thus there is **not yet** a flashable verified pair.

## Device gate
First test original working boot/vendor: SIM1 LTE with SIM2 3G; manually switch default mobile data SIM to SIM2, then inspect real registration. If SIM2 LTE works alone but not with SIM1 inserted, diagnose CP LTE-owner/RadioConfig handoff. If SIM2 cannot camp LTE even alone, investigate carrier/network/sim/CP instead. Detect actual physical LTE PS registration, not just supported bitmasks. Preserve TWRP rollback and bootable camera vendor. No simultaneous 4G+4G claim until **two independently verified WWAN PS HOME LTE registrations**.
