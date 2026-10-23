# ALICE Android 16 / Galaxy S8+ — SIM-working boot + vendor reference (23 Oct 2026)

**State: experimental branch only. Not device-verified on the newer kernel, not flash-ready.**

## Owner-supplied reference

The owner states this pair has normal SIM service; this is an **owner runtime report**, not a claim that a new build has passed on-device acceptance.

| Input | SHA-256 | Evidence |
| --- | --- | --- |
| `boot.img` | `9012313ab3d8b2e15fe00871da4872d4d09f7068211b36604eede6fe138c646b` | Android bootimg, dream2lte, Exynos8895; kernel 4.4.302 built Jun 1 2026 with Android Clang 11 |
| `vendor.new.dat.br` | `d84175ad36853683e4758d52d8ac361066d739fa3cbbe2ca1fc65529ff30fe94` | Brotli OTA payload, decoded and reconstructed as an EROFS filesystem |
| `vendor.transfer.list` | `c67cb9d75b3143c7ea9afe1ec1331e1a9bff1dcb7f036175e9c2000f0c7002a1` | OTA block transfer map, version 4 |
| Reconstructed EROFS | 499,060,736 bytes | Geometry and magic verified; not a flash partition size check |

Reference `boot.img` does **not** match the later ALICE V12R69 R16 kernel. Never replace R16 Image/DTB/ramdisk based only on this user report. A kernel modem-driver binary transplant has not been attempted.

## Byte-verified radio configuration comparison

Four *small text* files were extracted from the reconstructed EROFS without running firmware. The reference files and the original `baseline/test7` have identical SHA-256 digests:

- `etc/init/init.vendor.rilcommon.rc`: `c61001ec4a485b436c99fb2d55786aabd92d6fc9f5e4b1b9beff458eb31be610`
- `etc/init/vendor.sem.rilchip.rc`: `f3e6eb2e5330a3ba5e1a650ca6fc39b0b9ba25b9843743b7da8f15632a83380f`
- `etc/vintf/manifest/vendor.samsung.hardware.radio_manifest_2_33.xml`: `f7d0dfced1b52feb24202d9d8ce1e179dfd67f4c57d42081f57171da03922f2f`
- `etc/vintf/manifest/vendor.samsung.hardware.sehradio_manifest_2_33.xml`: `ad87982c72367cea3f368a023db52ef9a0b7da512d2b9689db8e3ccd89987afe`

The reference includes `IRadio/slot1`, `IRadio/slot2` and Samsung `ISehRadio` slot1/slot2. `rild`, `libsec-ril.so`, `libril_sem.so` and `secril_config_svc` **match the existing GitHub tree in file sizes**. Binary contents in the compressed OTA were **not hash-verified**; identical sizes alone do not establish identical libraries.

## What changed in this isolated research branch

Base: `work/a16-shutter-lag-photo-fast-feature-gate` — the user's camera/Video6 working candidate. Protect that original branch.

1. Restore `vendor/etc/init/init.vendor.rilcommon.rc` **byte-identically** to the owner-supplied reference, including the original late `setprop ro.telephony.default_network ${ro.vendor.radio.default_network}` after `network_config`. This is an A/B experiment, **not** a proven fix.
2. Preserve the early Android 16 `ro.telephony.default_network=9,9` declaration, the two radio HAL slots, all original radio binaries, Samsung Camera Preview/Picture/Video6 implementation and the two existing shutter-latency trial flags.
3. Add `tools/test_sim_reference_regression.py` and CI guards for source checksums, RIL binaries (versus the original GitHub manifest, not the OTA), and scope control.

**Known important limitation:** `ro.*` properties are read-only once set. Android 16 may reject the restored late `setprop`; the original property may already be `9,9`. A matching source is **not** proof of a working radio stack or a change in observed SIM registration. This A/B branch is useful only with device evidence. No fabricated LTE capability and no modem CP, NV, EFS, IMEI or modem calibration changes.

## Device acceptance before promotion (read-only)

Compare the currently working system and a **separately authorized recovery-capable A/B test**, ensuring the actual image fits the vendor partition and backup/rollback is proven. Check, without publishing phone numbers or IMSI/IMEI:

- After boot, verify both physical SIMs are detected and can register normally; separately test calls, SMS, mobile data, and switching default data SIM.
- Capture `getprop ro.telephony.default_network`, `getprop ro.vendor.radio.default_network`, `getprop ro.vendor.multisim.simslotcount`, `getprop persist.radio.multisim.config`, then examine filtered RIL init errors for `property already set` / `read-only` issues.
- Check both `dumpsys telephony.registry` / `dumpsys phone` carefully **on the device only** and redact private phone identifiers before sharing summaries. Confirm mobile network registration per phoneID, not just LTE in a supported RAF list.
- Confirm Samsung Camera preview, still capture, Video6 recording and playback remain functional, on both rear and front where supported.

If no measurable SIM improvement or any camera regression, revert **this branch only** and keep the existing working source. **CI PASS does not mean flash-ready**.
