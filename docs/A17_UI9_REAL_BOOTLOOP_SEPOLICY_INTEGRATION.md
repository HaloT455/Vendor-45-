# Android 17 / One UI 9 vendor integration — Galaxy S8+ (S8+ real bootloop)

## Baseline

This branch is based on the verified One UI 8 vendor used on `dream2lte`,
`work/a16-sim-reference-boot-vendor-20261023`. It retains Samsung Exynos8895
GPU/Mali-G71, camera, Gatekeeper/Keymaster and radio vendor assets.
**No vendor binary or SELinux rule has yet been changed on this branch.**

## Actual Android17 bootloop

`/system/bin/secilc` aborts when it combines A17 SYSTEM platform SELinux
and the existing vendor. In the first fatal failure, Android17
`plat_sepolicy.cil:314` gives `sysfs /bus/usb/devices` the label
`sysfs_usb`, whereas vendor `vendor_sepolicy.cil:1068` gives that same
path `sysfs_ss_writable`.

An experimental **SYSTEM-only** policy edit on a private CI copy resolves
that first conflict; however, Android17 native secilc subsequently reports
many `neverallow` violations from the VNDK33 vendor policy mapping.
**Thus there is NO valid or bootable port produced by the first edit.**

Private integration evidence:
- https://github.com/HaloT455/Dre/issues/1
- https://github.com/HaloT455/Dre/actions/runs/40616204342
- https://github.com/HaloT455/Dre/actions/runs/40616877172

## Engineering decision

1. Keep vendor HAL binaries identical until actual userspace compatibility is
   established. Do not randomly replace Mali, Gralloc, camera, RIL or TEE.
2. Create matched **Android17 platform + Exynos8895 vendor split sepolicy**,
   honoring neverallow restrictions and VINTF interfaces.
3. Test A17 native ARM64 `secilc` before rebuilding any vendor EROFS.
4. Rebuild only after a narrowly scoped, reviewable policy update.
5. Keep existing One UI 8 ROM usable for rollback, including banking profiles.
6. Do not flash files from this branch without verified matching SYSTEM and boot.

**BOOT_READY=NO. BANKING_READY=NO.** Enabling permissive mode, bypassing
neverallow or patching Google Play Integrity is explicitly not a port.
