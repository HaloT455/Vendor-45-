# ALICE full-vendor compatibility with Android 16 / SDK 36

## 1. Correct version semantics

Android 16 is framework **API level 36**, **not** VNDK 36. Official AOSP ended development of new VNDK starting with Android 15 and retained old VNDK APEXes to run existing vendor images. A fake `ro.vndk.version=36` can break system dynamic-linker namespace and native HAL loading. Do not edit `ro.vndk.version`, `ro.vendor.build.version.sdk`, `ro.board.first_api_level`, or VINTF `target-level` merely to increase numerals.

Official docs: https://source.android.com/docs/core/architecture/vndk

## 2. Actual Test7 starting point

- `vendor/build.prop`: `ro.vndk.version=33`, `ro.vendor.build.version.sdk=33`, `ro.product.first_api_level=24`, SoC Exynos8895.
- `vendor/etc/vintf/manifest.xml`: `target-level=4`, SEPolicy `33.0`. Device compatibility matrix requires vendor-NDK 33.
- Legacy Samsung-specific HAL interfaces and Android HIDL services are present; modern framework features often require AIDL service translation rather than properties.
- Vendor advertises face AIDL v2 and contains a vendor face service and face APEX. It is **not evidence** that the framework registers a running service or that enrolling/unlocking works.
- Vendor contains Exynos OMX AVC/HEVC encoders, Codec2 component/store, media profiles and XML. It is **not evidence** that Samsung Camera 16.5 has correct video-session/vendor-tag state or that its runtime video pipeline works.
- `ro.hardware.chipname=exynos9820` while SoC field is Exynos8895. This is a possible inherited mismatch, **not** permission to change it without testing vendor feature selection.

## 3. Scope of this branch

Branch `work/android16-vendor-compat` starts from the latest **vendor** work branch, not the kernel repository. Unmodified original `baseline/test7` persists. The first CI phase enumerates *every* vendor ELF executable and shared library, its ELF bitness and `DT_NEEDED` dependencies, plus VINTF contract and native camera/video/face components. The audit does not claim that external-to-vendor libraries are missing because framework or APEX may supply them. It reports external dependencies for actual device/runtime verification.

Use:

```bash
python3 tools/audit_android16_vendor_abi.py --selftest
python3 tools/audit_android16_vendor_abi.py --output out/android16-vendor-abi-audit.json
bash tools/audit_camera_video_face_runtime.sh
```

## 4. Migration gates to be passed before any vendor release

1. **Android 16 linker/ABI**: check 32-bit and 64-bit HAL dependencies resolve in actual framework/APEX; collect linker namespace and `CANNOT LINK EXECUTABLE` logs, audit legacy VNDK33 APEX provision.
2. **Video Camera**: check SamsungCamera video stream configurations, session transition, recorder surface, MediaCodec encoder startup, Exynos MFC nodes, Codec2 / OMX services; compare actual recording and playback. Preserve the two proven Samsung photo/preview metadata tags.
3. **Face unlock**: validate `IFace/default` AIDL registration, `sec-biometrics-face-aidl` process, face APEX contents, SELinux denials, camera/IR provider availability, and authentication/enrollment callbacks. Never assume a present service binary means a working sensor/driver.
4. **Platform interfaces**: audit graphics composer, gralloc, audio, sensor, Wi-Fi, GNSS, radio/IMS and security HAL behavior under the Android16 framework.
5. **System + vendor integration**: only after each component passes, consider replacing or adapting individual libraries/services using actual Exynos8895-compatible sources, with SONAME, ABI, SELinux and VINTF checks. Test rollback and partition size prior to flash.

**CI is read-only.** Vendor API and VNDK properties remain honest; no arbitrary ABI-wide conversion is feasible from binary-only vendor files. Full Android16 compatibility requires device runtime evidence and potentially matching framework/system changes, especially face unlock. Native kernel development remains suspended by user request.

## 5. Android 16 runtime verification on actual S8+

Static CI scanned **768 vendor ELF files** (95 camera-related, 83 video-related, 26 face-related) with zero initial structural blockers, but this is NOT a passing live Android16 ABI/HAL test. To gather evidence without modifying the device:

```bash
curl -fsSL https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/android16-vendor-compat/tools/collect_android16_vendor_runtime.sh -o ~/Downloads/ALICE_ANDROID16_RUNTIME.sh
bash ~/Downloads/ALICE_ANDROID16_RUNTIME.sh
```

The script creates `~/Downloads/ALICE_A16_VENDOR_RUNTIME_*.tar.gz`. Review sensitive log lines before sharing. Check API36 framework, legacy VNDK33 APEX, linker failures, HIDL/AIDL registration, media codec and face services. Only replace real Exynos8895-native components with proven ABI-compatible counterparts. Keep the kernel suspended and preserve currently functional Samsung Camera still/preview stack.
