# ALICE S8+ Android16 — Camera metadata fast-path + real Face/Iris audit

**Status: EXPERIMENTAL SOURCE ONLY. NO confirmed new flashable vendor build, no device-verified speedup, no restored biometric unlocking.**

## Source of truth

- Original known-working Samsung Camera + Video6 experimental branch:
  `work/a16-camera-video6-metadata-fix`, commit `6285b458a3f5d8a723fb7a1b80f0c22889007f9d`.
- Research branch: `work/a16-camera-fast-metadata-face-iris-audit`.
- Git compare confirms exactly one native Camera C file changed, plus diagnostics/test/CI workflow; **NO input vendor/ metadata bytes changed**.
- Build pipeline is `.github/workflows/alice-a16-camera-fast-face-iris-audit.yml`; image **only exists if CI completes and publishes artifact**. Do not claim the workflow has run unless verified.

## Camera path investigated

`vendor/etc/init/vendor.samsung.hardware.camera.provider@4.0-service.rc` already specifies `ioprio rt 4`, `capabilities SYS_NICE`, `task_profiles HighPerformance CameraServiceCapacity`. Adding arbitrary CPU boost settings can waste battery and cause thermal throttling; do not assume it improves JPEG shutter.

`tools/native_camera/alice_preview_bridge.c::wrapped_get_info` previously guarded **every** Camera2 static metadata read with the same process-wide `pthread_mutex_t`, although the `static_metadata[id]` result stays immutable for the module's process lifetime. Candidate fast path uses `__atomic_load_n(...,__ATOMIC_ACQUIRE)` for already initialized metadata. On first read, the code enters the mutex, builds Samsung Preview/Picture/6-int Video metadata and publishes with `__atomic_store_n(...,__ATOMIC_RELEASE)`. Delegated native Camera HAL still provides `get_camera_info` and performs all capture operations.

This can reduce subsequent Camera2 metadata lock contention. **It does not directly accelerate sensor readout, autofocus, HDR, JPEG encoding, shutter callbacks or the Camera app itself.** Before/after timing on actual device is required, and the original Video6 must not regress.

## Face Unlock path

Original vendor contains:
- `vendor/bin/hw/vendor.samsung.hardware.biometrics.face-service`
- `vendor/etc/init/face-default-sec.rc`, startup class `hal`
- `vendor/etc/vintf/manifest/face-default-sec.xml`, AIDL `android.hardware.biometrics.face` v2 `IFace/default`
- `vendor/lib64/android.hardware.biometrics.face-V2-ndk.so`
- `vendor/lib64/libFaceService.so`

This is **only a declared Face HAL**. It is not proof the service runs, registers Binder, publishes real physical sensors, has matching Samsung framework, communicates with Camera/TEE, enrolls a face or unlocks.

**Do not** substitute a generic Android virtual-face HAL, set fictional sensor IDs/strength, automatically force privilege grants, or synthesize authentication: would create a false security guarantee. Fix must preserve real authentication lifecycle, liveness constraints, device credentials and biometric class.

## Iris unlock path

Samsung's Galaxy S8/S8+ has a **dedicated IR iris camera and IR LED** separate from RGB selfie camera, documented in Samsung Newsroom.
https://news.samsung.com/global/in-depth-look-samsungs-biometric-technologies-bring-added-security-and-convenience-to-the-galaxy-s8

The current **vendor file inventory** does not contain filenames identifying an iris-specific HAL/service. **This cannot establish hardware absence**, but is a significant indication this newer Samsung port lacks a legacy-compatible iris pipeline. Iris unlock requires matching real sensor transport, firmware/TA/TEE integration, OS biometric service and lockscreen enrollment. Advertised `android.hardware.biometrics.iris` in an XML is not enough. Don't spoof service or enable IR emitter blindly.

## Read-only Zorin diagnostics — no raw logs saved

```bash
curl -fL --retry 2 \
  https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-camera-fast-metadata-face-iris-audit/tools/alice_camera_face_iris_device_audit.py \
  -o "$HOME/ALICE_CAMERA_FACE_IRIS_AUDIT.py"

python3 "$HOME/ALICE_CAMERA_FACE_IRIS_AUDIT.py" \
  --output "$HOME/ALICE_CAMERA_FACE_IRIS_SAFE.json"
```

Optional one-shot app startup check (not actual shutter timing):

```bash
python3 "$HOME/ALICE_CAMERA_FACE_IRIS_AUDIT.py" --launch-camera
```

Device output only contains whitelisted service statuses, feature presence, error counters and optional activity start time. Never upload `dumpsys face`, `dumpsys biometric`, raw logcat, face templates, private keys, SIM identifiers or plaintext credentials.

### Interpretation

1. If `face_init_service` not `running`: inspect init failures, ELF DT_NEEDED dependencies and SELinux denials before changing RC or packaging a new face HAL.
2. If service running but `face_aidl_binder_registered=false`: inspect interface registration, VINTF/SELinux, ABI and framework expectations.
3. If Face Binder registered but `face_sensor_properties_mentioned=false`: identify true physical sensor path and HAL support, not just overlay feature config.
4. If Face publishes a real sensor but Settings lacks enroll: inspect Samsung One UI8 `SemBiometric` and framework code from SYSTEM V2 read-only copy, not arbitrary Vendor APK.
5. If Iris service absent: find stock Exynos8895 legacy iris service/TEE ABI and secure bridge strategy; likely requires SYSTEM AND VENDOR changes, not just vendor. Never assume iris 1:1 backward-compatible with Android16 modern AIDL.

**No new image should be flashed solely because this audit identifies a service or a cache optimization. CI image is research-only and requires verification of actual vendor partition geometry, Camera rollback, and real device latency.**


## 2026-10-22: Blank Face setup and missing Iris menu confirmed by device user

User reports that **face enrollment screen does nothing** and **iris enrollment option is absent entirely** after experimenting with vendor. These are NOT solved by the camera metadata fast-path.

The locally extracted, camera-working SYSTEM V2 directory exists on Zorin at:
`/mnt/alice-ssd/ALICE_SYSTEM/GITHUB_SYSTEM_V2_IMPORT/SystemDreamlte/system`
(under it, for example: `system/priv-app/SecSettings/SecSettings.apk`).

The GitHub **SystemDreamlte** repository still lacks `baseline/system-v2-camera` (only `main`), so inspecting it remotely cannot resolve the missing Samsung Settings code.

New read-only tool: `tools/alice_system_v2_face_iris_audit.py`. Run on Zorin against extracted SYSTEM V2, no re-extraction or Git upload needed:

```bash
curl -fLsS "https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-camera-fast-metadata-face-iris-audit/tools/alice_system_v2_face_iris_audit.py" \
  -o ~/ALICE_SYSTEM_V2_FACE_IRIS_AUDIT.py
python3 ~/ALICE_SYSTEM_V2_FACE_IRIS_AUDIT.py --output ~/ALICE_SYSTEM_V2_FACE_IRIS_REPORT.json
```

Also run existing read-only device audit to get Face HAL initialization, Binder registration, presence of actual sensors, high-level error counts only:

```bash
curl -fLsS "https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-camera-fast-metadata-face-iris-audit/tools/alice_camera_face_iris_device_audit.py" \
  -o ~/ALICE_CAMERA_FACE_IRIS_AUDIT.py
python3 ~/ALICE_CAMERA_FACE_IRIS_AUDIT.py --output ~/ALICE_CAMERA_FACE_IRIS_SAFE.json
```

Both JSON reports contain **no biometric template data**, no raw logcat and no SIM/IMEI information. Display only the JSON to the researcher.

**Cross-check:** If the AIDL HAL is not operational, investigate libraries, service registration and SELinux; if registered but no physical sensor, investigate genuine Samsung face sensor back-end. If local SYSTEM V2 Settings lacks iris UI code, an Android16-compatible Settings and secure iris service integration is required. No fabricated AIDL HAL, no simulated biometric pass events, and never manually energize the iris IR LED because Samsung's hardware safety restrictions matter.

Official Samsung details: S8 has a dedicated IR iris camera/LED and specific automatic shutoff/safety behavior:
https://news.samsung.com/global/in-depth-look-samsungs-biometric-technologies-bring-added-security-and-convenience-to-the-galaxy-s8
https://www.samsung.com/hk_en/support/mobile-devices/galaxy-s8-is-it-harmful-being-ir-irradiated-on-the-eyes-for-authentication/

AOSP Android16's published biometrics HAL directory contains `common`, `face`, `fingerprint` only, requiring OEM-specific integration for iris:
https://android.googlesource.com/platform/hardware/interfaces/+/android16-release/biometrics/

**No new vendor flash is justified for these features until runtime Face diagnostics and local SYSTEM V2 UI inventory are reviewed.**
