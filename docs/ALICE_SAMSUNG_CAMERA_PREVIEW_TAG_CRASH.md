# ALICE S8+ Samsung Camera: Preview metadata failure, 17 October 2026

**Private evidence:** User-provided ADB package dump, camera_service and logcat reviewed locally. No private APK or raw logs committed. Any live build below still requires phone tests.

- Installed Samsung Camera package `com.sec.android.app.camera`, version **16.5.02.48**, is located in `/data/app`. This differs from UN1CA S9+ reference **16.0.00.74**.
- Initial camera 0 opens successfully through legacy ExynosCamera3; the provider does not crash before the app.
- `CameraService` lists only **9 Samsung vendor tag definitions** and lacks `samsung.android.scaler.availablePreviewStreamConfigurations`.
- Standard `android.scaler.availableStreamConfigurations` includes **[34,1440,1080,OUTPUT]** on camera 0; legacy camera1 also advertises 1440x1080.
- On launch, `SemCameraCharacteristics` logs that the Samsung preview configuration tag is unsupported, then PreviewManager says `Not supported preview size!(1440x1080)` and `Changed to optimal preview size!(null)`.
- **First fatal:** `java.lang.NullPointerException` at `com.sec.android.app.camera.preview.PreviewManagerImpl.changePreviewSurfaceSize`, 23:59:27.190. CameraDeviceClient errors *after* process death are consequences, not causes.
- Other tags are also missing (availableFeatures, afAvailableModes, aeAvailableModes, colorSpaceAvailableModes, etc.), and might become later failure points after the first is fixed.

## Recommended repair architecture (not yet implemented)
- Fix the OEM vendor-tag contract at Camera HAL / provider boundary: **register** `samsung.android.scaler.availablePreviewStreamConfigurations` without losing the 9 legacy tags, and populate **actual per-camera static characteristics** derived from the already advertised Camera2 output stream configurations. Validate array element type/count, characteristics keys and sizes: a name-only synthetic tag won't work.
- Do not blindly inject unsupported dimensions or splice Exynos9810 machine code into Exynos8895.
- Alternative APK Smali fallback: for *this exact* SamsungCamera 16.5.02.48, fall back to AOSP StreamConfigurationMap when the Samsung vendor tag is absent. Requires APK modification/re-signing with suitable keys and cannot be installed as a seamless update over the Samsung-signed app without signing compatibility.
- Keep the previous Test7 baseline, validate 32/64 ABI, SELinux, EROFS, Android's vendor-tag registration and physical preview/JPEG before offering any flash-ready artifact.

## Regression guard
`python3 tools/camera_preview_contract.py --selftest`

For fresh on-device dumps extracted locally:
`python3 tools/camera_preview_contract.py --camera-service camera_service.txt --log camera_error.log --output result.json`

**Current state: confirmed first failure; not repaired; prior experimental vendor.img is still not flash-ready.**
