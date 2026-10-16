# ALICE investigation: public UN1GAGA Exynos8895 port (16 Oct 2026)

Primary upstream: https://github.com/nhglong/UN1GAGA/tree/sixteen-8895
Pinned head: 5b73038bc943d8b8d3d0d6ef83588eea5a87b63c
Developer release (14 Oct 2026): https://t.me/hlongupdates/207

## Directly verified source

1. Author wraps the S8/Note8 legacy HAL, not by renaming an interface.
   https://github.com/nhglong/UN1GAGA/commit/e9cf13b27abb410f9cc4ba4b66dcdee1c5e42e03
   Upstream introduces camera.universal8895.so (32/64) as a wrapper and
   renames the original camera.universal8895.so to
   camera.vendor.universal8895.so. Wrapper forwards original operations
   and adds set_torch_mode_strength when the underlying HAL lacks it.
   Commit description explicitly targets Note8 flashlight behavior;
   it DOES NOT claim to fix Samsung Camera OEM application on S8+.

2. Camera fence lifetime/shim fix:
   https://github.com/nhglong/UN1GAGA/commit/559ad15e25f3bbcc8f2e6a490f03bbe553401db7
   Upstream states old HAL leaks acquire fences/fds. Replaces
   Fence symbols in libexynoscamera*.so, uses libshim_camera.so.
   Repeating patch blindly may invalidate ELF symbols or duplicate it.

3. Framework physical SIM slot configuration:
   https://github.com/nhglong/UN1GAGA/commit/bf675873b3170811fed153920d368354be03dbcc
   Adds config_num_physical_slots=2 via vendor RRO for pre-API36
   and a matching Samsung secril_config_svc.
   This configures TWO PHYSICAL SLOTS, not dual-active LTE.
   ALICE current OneUI8 SDK36 and vendor API33 need checking before
   adapting RRO; the upstream condition is on TARGET_PLATFORM_SDK_VERSION.

4. Upstream platform/exynos8895/patches/camera/customize.sh explicitly
   removes the SamsungCamera system app. This confirms that a fix in
   UN1GAGA generic camera is NOT proof OEM Samsung Camera now works.
   https://github.com/nhglong/UN1GAGA/blob/sixteen-8895/platform/exynos8895/patches/camera/customize.sh

## Exact Git blob comparison: ALICE Test7 vs public 8895 port

Compared the pinned public tree to our work/camera-sim tree on
16 October 2026. 1079 vendor paths overlap; 510 have identical Git blobs.
The source references below are whole-file blob IDs, *not runtime validation*.

| Component | ALICE Test7 blob | UN1GAGA source blob | Conclusion |
|---|---|---|---|
| vendor/lib/hw/camera.universal8895.so | 9752d2976103edbf7855530ce9fae717bbe4df39 | upstream original camera.vendor.universal8895.so has SAME blob | ALICE has original HAL, no wrapper |
| vendor/lib64/hw/camera.universal8895.so | 72e9846c6aec469960f89e4d86850939aab0daeb | upstream original camera.vendor.universal8895.so has SAME blob | ALICE has original HAL, no wrapper |
| UN1GAGA 32-bit camera wrapper | not installed | c3e756812b8d2ab0574321927a47fd59612d7d13 | candidate adapter |
| UN1GAGA 64-bit camera wrapper | not installed | 3e6bfbfa94fd5f23d5877a882dc49b7b8b98da50 | candidate adapter |
| vendor/lib/libshim_camera.so | 2ddd1d265fae45fc1097bec39118dfe4624bcf28 | SAME | Already present, do not recopy |
| vendor/lib64/libshim_camera.so | 4e78d8c5ec161daac5e39acca8d7ecbbb855637f | SAME | Already present, do not recopy |
| vendor/lib64/libril_sem.so | a03d90f8c0034bbf71ec7d8be05400ce2370d675 | SAME | No fix by recopying |
| vendor/lib64/libsec-ril.so | d92b206e128163313a1755054358ae5944fb3203 | SAME | No fix by recopying |
| vendor/bin/hw/rild | 18622cc72d3e09cdb7586a0b7c55a728e2889789 | SAME | No fix by recopying |
| vendor/lib/libexynoscamera3.so | 9f598586aaca1d67b2f30a3258095d107bf3f058 | 654a33031c200a6c5f0a2cf3c5f0cf86a86713f4 | Changed: inspect ABI and fence logic |
| vendor/lib64/libexynoscamera3.so | 2f9ca05e7a4b0a56127eeabe7133d52407f5476a | 978ccc57c0697041875466bc45825d594f915a16 | Changed: inspect ABI and fence logic |

## Port design (NOT applied to shipping vendor)

- Stage both exact pinned wrapper .so files from the public repo.
- Preserve original HALs byte-for-byte at the new
  camera.vendor.universal8895.so paths in a SEPARATE experiment.
- Change metadata (fs_config, SELinux contexts, EROFS manifest)
  consistently; validate ELF 32/64 dependencies and HAL loader behavior.
- Do NOT port arbitrary system/framework Camera APK or modified
  libexynoscamera binaries without source-vs-runtime ABI review.
- No changes to CP, NV/EFS, IMEI or modem provisioning.
- Build in CI; install on device only after an explicit test and
  rollback plan. An offline EROFS build does not prove successful boot.

The UN1GAGA release claims to fix camera functionality; neither
the port's source history nor existing ALICE logs proves that it
upgrades the OEM Samsung Camera HAL or enables dual-active 4G.
