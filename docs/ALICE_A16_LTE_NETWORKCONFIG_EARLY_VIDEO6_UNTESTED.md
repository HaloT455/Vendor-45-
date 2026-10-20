# ALICE Android 16 Exynos8895 — LTE NetworkConfig Early + Camera Video6 experiment

**STATUS: vendor research image / NOT FLASH VERIFIED / no LTE attach proven.**

## Hypothesis and evidence

The user's Galaxy S8+ `dream2lte` Android 16 One UI 8 shows SIM1 `CS DENIED/PS NOT_REG_OR_SEARCHING` on UMTS and SIM2 `HOME/UMTS+HSPA+`, while `ro.telephony.default_network=9,9`, `ro.vendor.radio.default_network=9`, both user LTE masks and the active framework RAF RRO already permit LTE. Logs show eight **historical** `setPreferredNetworkType: Abort, unknown RAF: 0` events at 11:37:10–11:37:15 on 2026-10-20; neither phone ID nor current persistence of RAF0 is known.

AOSP `Phone.updateAllowedNetworkTypes` aborts if cached modem RadioCapability RAF=UNKNOWN; the existing resource `config_radio_access_family=GSM|CDMA|EVDO|WCDMA|LTE` is active. Stock Samsung `secril_config_svc NetworkConfig` reads `/mnt/vendor/efs/telephony.prop` and attempts to set `persist.radio.def_network` and `ro.vendor.radio.default_network`, when present. The former is empty at runtime, the latter is 9. This is **not** proof of misconfiguration, as EFS may lack the field or property setting may be blocked.

**Trial hypothesis:** Samsung NetworkConfig's prior `post-fs-data` execution might occur after certain early vendor radio initialization, contributing to stale RadioCapability. Trial runs the *unchanged original network_config one-shot* during `on fs`, **after** `sim_config`. No new service, property or made-up modem RAF is introduced. The Samsung one-shot program may fail if telephony.prop is not yet accessible; runtime logs are required to distinguish this possibility.

This **does not directly repair a HAL response of SUCCESS+RAF0**. The separate Android framework fallback research branch (`work/a16-raf0-framework-fallback-study`) is source-only, not an installable fix.

## Diff constraints

Base commit / camera branch: `work/a16-camera-video6-metadata-fix`, commit `6285b458a3f5d8a723fb7a1b80f0c22889007f9d` — previously user-reported working Camera+Video6.

Exactly **one input vendor file** differs:

- `vendor/etc/init/init.vendor.rilcommon.rc`: one `exec_start network_config` moved from `on post-fs-data` to `on fs` immediately after `exec_start sim_config`.

**Unchanged:** vendor camera HAL metadata & video recording wrappers, Samsung radio HAL & `libsec-ril.so`, framework RAF RRO, modem/CP firmware, EFS & NV & IMEI, kernel, preferred network `9,9`, DSDS flags, VNDK33 Android16 bridge.

## Isolated GitHub CI

`.github/workflows/alice-a16-lte-networkconfig-early-video6.yml`:
- Hard fail if baseline altered or any input vendor/metadata files other than single init RC are changed from working Camera+Video6 branch.
- Build the **identical camera preview bridge** and six-field video configurations from Camera+Video6 branch, retaining both camera ABI variants.
- Build EROFS from SHA-pinned original metadata; verify path, uid, gid, mode, SELinux xattrs, superblock features, extracted content, header and SHA256.
- Cap experimental image size at 481,931,264 bytes. **Size <= cap is NOT proof image fits the user's vendor block device**.
- Save image as `out/vendor-a16-video6-lte-networkconfig-early-UNTESTED.img` and report/checksums in one artifact named `ALICE-A16-LTE-NETWORKCONFIG-EARLY-VIDEO6-UNTESTED-NO-FLASH`.

## Gate before ANY device installation

1. Confirm real partition geometry `blockdev --getsize64 /dev/block/by-name/VENDOR` or equivalent by-name path (read-only), compare image size; test backup and verified recovery restore. Never dd a larger image to physical partition.
2. Preserve booting Camera+Video6 image and tested restoration procedure. Inform user trial may cause loss of cellular connectivity.
3. If flashed safely after owner approval, check initial radio service errors, SIM slots, LTE attach via per-slot WWAN registration. Do NOT use `allowed LTE` as a result.
4. If LTE still absent, return to exact working Camera+Video6 image and investigate `getRadioCapabilityResponse` on the proprietary HAL. No LTE fix may be claimed from CI-only validation.

**This is a non-flash-verified radio startup timing experiment, not a verified LTE repair.**
