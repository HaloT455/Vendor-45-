# ALICE A16 S8+ — camera self-close regression and DSDS vendor merge (19 Oct 2026)

## Observed reproducible failure (from a user-uploaded read-only log)

Samsung Camera `com.sec.android.app.camera` launches and contacts Camera1 but terminates about 0.4 seconds after preview size calculation on 2026-10-19 23:37:21. The first cause is:
- `SemCameraCharacteristics`: Samsung-specific `samsung.android.scaler.availablePreviewStreamConfigurations` key is unavailable.
- PreviewManager: `Not supported preview size!(1440x1080)`; fallback `Changed to optimal preview size!(null)`.
- `FATAL EXCEPTION: main`, `NullPointerException` in `PreviewManagerImpl.changePreviewSurfaceSize`.
- Subsequent CameraService `binderDied` and ExynosCamera3 cleanup errors follow the application crash; do not misidentify as the original cause.

The last DSDS-only EROFS build compiled the source camera HAL without the ALICE supplemental Samsung vendor-tag bridge. The earlier archived ALICE camera trials did stage camera wrappers, and an 18 Oct device run previously advanced past preview to an unrelated `ACCESS_SYSTEM_KEY_DISPATCHING` permission crash. Do not assume any prior image was fully working.

## Applied fix in this *separate work branch* (source build, not deployed)

Work from `work/dual-sim-lte-raf-trial`, retaining both:
- `vendor/build.prop`: `ro.telephony.default_network=9,9` for two DSDS phone IDs.
- `vendor/etc/init/init.vendor.rilcommon.rc`: no post-fs-data scalar overwrite of read-only `ro.telephony.default_network`.

The new CI reuses prior camera toolchain:
1. Fetch SHA-pinned 32/64 Exynos8895 UN1GAGA wrapper from `nhglong/UN1GAGA`; fail if blob hash mismatches.
2. Rename the source HAL to `camera.vendor.universal8895.so`, preserving original 32/64 blobs and metadata.
3. Compile `tools/native_camera/alice_preview_bridge.c` with pinned Android NDK, stage its 32/64 `camera.universal8895.so` and keep UN1GAGA delegates as `camera.alice-hlong.universal8895.so`.
4. Expose Samsung preview `availablePreviewStreamConfigurations` and picture `availablePictureStreamConfigurations` from actual format 34 PRIVATE / format 33 BLOB AOSP characteristics. Old original vendor tags stay delegated.
5. Preserve the legacy SIM2 3G service and HAL radio blobs, Face HAL and baseband unchanged.
6. Audit ELF symbol `HMI`, dependencies, manifest metadata, and rebuild EROFS with independent checksum report.

The bridge also currently exposes experimental Samsung `availableVideoConfigurations`; the original video tag schema remains **unverified** and cannot be relied on for working recording.

## Before a device flash

- The experimental CI image may exceed the original Test7 image size (481640448 bytes) or actual vendor partition size. **Do not flash it without checking device partition geometry**.
- Source CI cannot verify whether One UI 8 dynamically loads the camera module and metadata properly or whether a KernelSU overlay replaces one of the camera files.
- Preserve a backed-up bootable vendor image, confirm recovery access, verify boot/SELinux and app permissions.
- After an authorized, safe test, require Samsung Camera app to stay open at least 10 seconds, actual preview pixels, rear+front Camera2 characteristics, photo capture and release. Do not claim video and face unlock fixed.
- The previous system-key SecurityException after preview might recur. It is a separate system/app permissions problem not solvable solely through Camera HAL vendor tags.

### Invariants

The original `baseline/test7` is immutable. Modem CP/EFS, IMEI, KernelSU, Android framework, app APK and Samsung Radio HAL are not modified. All work is staged in CI on ephemeral checkout. **NOT FLASH READY.**
