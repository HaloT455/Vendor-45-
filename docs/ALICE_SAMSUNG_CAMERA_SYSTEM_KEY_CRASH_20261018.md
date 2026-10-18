# ALICE Samsung Camera 16.5.02.48: preview success, UI framework permission crash (18 Oct 2026)

## Exact evidence (private ADB archive, not committed)

Phone S8+ G955F Exynos8895; Camera2 metadata now exposes both Samsung scaler vendor tags:
- 0x80030000 `availablePreviewStreamConfigurations`;
- 0x80030001 `availablePictureStreamConfigurations`.
Real Camera preview images appear. The app proceeds to `CameraGenericEventHandler.onStartPreviewCompleted` at **09:25:44.505** on 2026-10-18, and then immediately Java-crashes **09:25:44.518**:

```
java.lang.SecurityException: Requires ACCESS_SYSTEM_KEY_DISPATCHING permission
  at android.view.IWindowManager$Stub$Proxy.unregisterSystemKeyEvent
  at com.samsung.android.view.SemWindowManager.unregisterSystemKeyEvent
  at com.sec.android.app.camera.CameraWindowManager.requestSystemKeyEvents
  at com.sec.android.app.camera.Camera.onCameraEnterCompleted
  at com.sec.android.app.camera.CameraGenericEventHandler.onStartPreviewCompleted
```

`dumpsys activity exit-info` marks PID **27584** as `APP CRASH(EXCEPTION)`.
The private package dump shows:
- SamsungCamera **16.5.02.48**, APK `/data/app/.../base.apk`, not installed as a privileged system app.
- Requested `com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING` is **absent from granted install permissions**.
- Samsung-signed APK original was provided privately and is not committed; its ZIP v1 cert subject includes Samsung Corporation (subject alone does not independently prove provenance).
- A separate `latest_tombstone.txt` included in the archive belongs to **Bluetooth native JNI**, not the Samsung Camera process: DO NOT diagnose Camera HAL from this unrelated tombstone.
- Other later `LOW_MEMORY` process-exit records are not the causal 09:25:44 exception.

## Decision

**DO NOT MODIFY native vendor Camera HAL for this crash.** The HAL preview pipeline works. The runtime gate is `WindowManagerService` enforcing a permission on `SemWindowManager.unregisterSystemKeyEvent`. Granting hardware camera HAL tags cannot affect system_server permission checks. A file in `/vendor/etc/permissions` alone does NOT privilege a package installed under `/data/app`.

**Preflight first**:
```bash
python3 tools/check_samsungcamera_key_permission.py
```
If the ROM declares `com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING` with `prot=signature|privileged` and the corresponding full privileged-permissions allowlist can be safely audited, systemizing the original signed app in `/system/priv-app` is a potential solution, but is NOT yet tested and must be reversible. This needs system overlay, not vendor-only payload. For `prot=signature` only, systemizing alone will not help unless app and permission owner share cert; consider an APK compatibility patch to gracefully catch the single SecurityException, mindful of Android signing restrictions. If the permission is undefined in the ROM, fix its definition/owner first.

Avoid trying `pm grant` on signature/privileged permissions; this does not make an arbitrary `/data/app` install privileged. Do not weaken or bypass WindowManagerService's global permission enforcement.

Next runtime acceptance gate is Samsung Camera remaining open after `onStartPreviewCompleted`, functional photo shutter and video recording; passing CI alone is not a device fix.

Kernel development suspended per user. Camera vendor source `work/camera-sim` only; original `baseline/test7` unchanged.
