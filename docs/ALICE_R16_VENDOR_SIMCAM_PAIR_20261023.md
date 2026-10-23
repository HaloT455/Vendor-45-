# ALICE S8+ R16 + Android16 Camera/Radio paired build — 23 October 2026

**PAIR_ID: ALICE-S8P-A16-R16-SIMCAM-20261023**
**Status: SOURCE-SYNCHRONIZED / DEVICE UNTESTED / NO-FLASH.**

## Sources locked by CI

- Boot/kernel source: `HaloT455/dream2lte-45`, R16 base commit `b892e28db47fb9aaf2df8d3196050a76288b6caf`.
- Vendor source: this branch based on `work/a16-sim-reference-boot-vendor-20261023` and proven-on-owner-camera candidate `work/a16-shutter-lag-photo-fast-feature-gate`.
- The peer R16 paired branch is `agent/v12r69-r16-paired-vendor-20261023`, with a source contract and a repacker that refuses incompatible legacy DH2 ramdisk.
- Owner reference boot SHA256: `9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b`, known working with the separately uploaded source vendor in user's report. **That boot has interactive+DH2, not R16 EnergyStep.**
- The working owner's vendor OTA (EROFS 499060736 bytes) carries unmodified Samsung RIL radio binaries. Radio HIDL files, `init.vendor.rilcommon.rc` and Samsung radio RC are byte-matched to Test7 source. Full OTA radio binaries not hash-verified.

## What is actually aligned

1. Kernel Kconfig modem symbols agree with owner reference `boot.img` IKCONFIG: `SEC_SIPC_MODEM_IF`, `SEC_MODEM_SS310AP`, `UMTS_MODEM_SS310AP`, `LINK_DEVICE_SHMEM`, `LINK_DEVICE_NAPI`, `SHM_IPC`, `MODEM_IF_QOS`, and EROFS.
2. Vendor retains `IRadio/slot1`, `IRadio/slot2`, `ISehRadio`, the original `rild`/Samsung radio HAL, early `ro.telephony.default_network=9,9`, and the reference `NetworkConfig` startup. The reference late `ro.*` write is still present as an experimental A/B. **Read-only Android16 property rules may reject it; this has not been proven to repair either SIM.**
3. Original Samsung Camera bridge and correct six-int Video6 metadata are preserved, plus two existing photo flags. No camera hardware changes.
4. Binary CP modem, EFS, NV, IMEI, radio calibration and the protected baseline branch are untouched. No false Dual-LTE capability is asserted.
5. Vendor CI checks pinned R16 source with `tools/test_sim_pair_contract.py`, runs legacy Camera/Video6/DSDS tests and builds an experimental vendor EROFS with checksum and report.

## GitHub Actions outputs

Run `.github/workflows/alice-a16-samsung-video6-fix.yml` from this branch:
- Artifact: `ALICE-S8P-A16-R16-PAIR-VENDOR-SIMCAM-UNTESTED-NO-FLASH`.
- Image name: `vendor-a16-sim-reference-video6-UNTESTED.img`.
- Contract report: `out/paired-simcam-contract.json`.

Peer kernel Actions from paired R16 branch build Image/dtb.img only, plus separate contract and SHA256. Those are **not yet a safe flashable boot image**: the user's old boot ramdisk contains unsupported `interactive`/DH2/HMP settings and cannot be blindly repacked with EnergyStep.

## Gates still required before release

Confirm R16 boots with a **verified R16-compatible** ramdisk and paired vendor image that actually fits the device's vendor partition. Use TWRP verified rollback. On physical SM-G955F check each SIM detects/registers, outgoing/incoming voice calls, SMS, data, data-SIM switching, idle/overnight state, Samsung Camera photo/front/back preview, six-int video capture/playback and thermal/suspend. Only after all acceptance checks promote source to stable.

**Neither an offline static PASS nor a green Actions build can claim both SIMs or Video6 work on this new pair.**
