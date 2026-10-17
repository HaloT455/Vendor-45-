# S9+ UN1CA / DuhanROM reference for ALICE S8+ Samsung Camera

Status: SOURCE RESEARCH ONLY. No S8+ hardware verification.

Source: Eend15/Unofficial-Un1ca-9810, Android-16 @ 2b25ae6fc3098650be249bd1898e21e563cd5df1 (GPLv3). Actual code is under unica/patches/exynos9810_device_stack/exynos9810_finalization/native_camera/.
DuhanROM source repository found (duhansysl/DuhanROM-Reports) contains bug reporting, not a verified public S8+ compatible app patch.

S9+ solution:
1. Keep One UI 8 system/priv-app/SamsungCamera APK v16.0.00.74, repair normal Photo AutoBeautyPhotoMaker Samsung-client routing while preserving the QR-only route. Avoid two shutter callbacks (Camera2 onCaptureStarted and PhotoMakerBase.sendCaptureAvailable) for the same JPEG. Disable unsupported automatic QR repeating preview stream for regular Photo.
2. Restore only target-matched Exynos9810 32/64-bit camera HAL/provider files after generic UN1CA changes.
3. Exynos9810-specific low-light 4-frame path is rerouted to a stable single-frame capture with ARM opcode patterns that differ per target. DO NOT transplant those bytes to Exynos8895.
4. Exynos9810 capture acquire-fence leak is handled by a verified native hook at the exact processCaptureRequest symbol, preserving ownership on rejected requests. DO NOT assume same symbol/ABI on Exynos8895.
5. S9+ tests show Photo JPEG capture working but normal-photo automatic QR disabled, and only short-duration stability evidence.

ALICE blockers:
- nhglong/UN1GAGA sixteen-8895 camera customization explicitly deletes the system SamsungCamera app. Its released S8+ Camera fix therefore is not proof of Samsung OEM Camera.
- HaloT455/Vendor-45- is vendor-only. The APK and Samsung framework JARs are system-partition inputs, not provided in this repo. A vendor.img cannot install a privileged system app.
- tools/s9_reference/ supplies the upstream S9+ Smali source patch and tests for layout reference. It must NOT be automatically applied to an unknown Samsung Camera version, nor does success prove a working S8+ app. Preserve matching ROM APK signing/permissions if later porting.
- tools/probe_samsung_camera_8895.py generates read-only native ABI evidence from the ALICE vendor source; decide whether a new 8895-specific fence adapter is valid only after examining this report.
- Need S8+ actual Samsung Camera fatal logcat, installed APK/system image and vendor tag runtime information. The earlier Aperture preview/JPEG success indicates basic Camera3 operation, not Samsung Camera availability.

Execution gating: identify first app-level failure -> confirm app present and system/priv-app privileges -> inspect Samsung-specific vendor tags and Camera2 metadata -> apply only layout-checked app smali on isolated decoded APK -> rebuild app + test with matching system files -> fix HAL if a native root cause remains. Backup, rollback, do not flash trial ROM without hardware validation.
