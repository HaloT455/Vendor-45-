# ALICE One UI 9 graphics HAL port preflight — S8+ Exynos8895

This is a **source/metadata preflight branch only**. It forks the verified
`work/a16-sim-reference-boot-vendor-20261023` branch and **does not**
replace existing GPU, gralloc, composer, camera, modem or other vendor binaries.

- Target: Samsung Galaxy S8+ `dream2lte`, Exynos8895, Mali-G71 MP20.
- Donor: privately held `HaloT455/Dre` One UI 9 SYSTEM, Android 17, SDK37.
- Donor SYSTEM SHA-256: `1a4f0b6a3f5ee9e5a70d69c715e0e98b57c8413d74e136e9e39d29648af8b3be`.
- Donor CI proof: successful read-only inventory (https://github.com/HaloT455/Dre/actions/runs/40573797827).
- Runtime compatibility CI: https://github.com/HaloT455/Dre/actions/runs/40576126218 (graphics preflight: BLOCKED_BEFORE_FLASH).

## Current baseline HALs

`vendor/lib{,64}/hw/android.hardware.graphics.mapper@2.0-impl.so`

`vendor/lib{,64}/hw/android.hardware.graphics.allocator@2.0-impl.so`

`vendor/lib{,64}/hw/gralloc.exynos5.so`

`vendor/lib{,64}/hw/hwcomposer.exynos5.so`

`vendor/bin/hw/android.hardware.graphics.allocator@2.0-service`

`vendor/bin/hw/android.hardware.graphics.composer@2.4-service`

`vendor/lib64/hw/vulkan.mali.so` is a symlink; inspect its target and dependencies before judging presence.

## Donor Gralloc4 package

The user provided an archive labelled Exynos 9610/9611. It must first pass
architecture, `DT_NEEDED`, VINTF, SELinux, sync fence, GPU driver,
allocator/mapper/gralloc handle layout and HWC 2.4 matching checks. Those
facts cannot be inferred from a file name. **Do not copy donor .so files
into this public vendor repo**, do not put donor HALs under `/system`,
and do not change SELinux to permissive as a shortcut.

The separate PRIVATE `Dre` repository contains a
`tools/audit_gralloc4_zip.py` script and workflow
`.github/workflows/audit-gralloc4.yml`. Store proprietary donor ZIP
only in a PRIVATE release there, and publish metadata reports only.

## Test gates

1. Inspect donor ZIP and confirm native ELF architecture + symbol/link dependencies.
2. Verify target Android 17 graphics interface version and linker namespaces.
3. Build/derive Exynos8895-specific mapper+allocator with matching Mali-G71 handles.
4. Check VINTF, init service, SELinux labels and graphics service registration.
5. Preserve working vendor and boot baseline for rollback.
6. Obtain device runtime captures (`lshal`, `dumpsys SurfaceFlinger`, graphics kernel logs).
7. Only after all passing, produce an isolated, reversible test candidate.

**FLASH_READY=NO**. No flashable image or ROM is released from this branch.
