# ALICE Camera Shutter Delay (4–5 s) — Scene Optimizer / Auto Night AB Trial

**Status: NEW EXPERIMENTAL VENDOR IMAGE — NOT confirmed to reduce shutter latency or to boot safely.**

## User observation and separate biometric facts

- The Samsung Camera app is now able to take photos and Video6 works; shutter visibly occurs **4–5 seconds after tap** in Photo mode.
- Camera metadata lock-free fast path helps repeated metadata enumeration, not actual `captureRequest`, JPEG encoding or HAL 3A pipeline.
- Direct ADB face report from device: `face_init_service=running`, Face AIDL Binder registered, `face_sensor_properties_mentioned=true`, but **face enrollment UI is blank/not functioning**.
- SYSTEM V2 has `SemIrisManager` and `IrisService` symbol strings in framework and `IrisEnroll` in SecSettings/SystemUI, but `iris_feature_advertised=false`, no named iris vendor HAL/service. No face/iris fix is in this camera experiment.
- SYSTEM V2 framework contains `android.hardware.biometrics.face-V4-ndk.so` while vendor has V2. This difference in interface library filename/version is not independently sufficient to diagnose incompatibility; the live interface registration proves partial functionality.

## One-variable-class photo experiment

From baseline `work/a16-camera-fast-metadata-face-iris-audit` (already Camera + Video6-capable), change ONLY:

```diff
-<local name="SUPPORT_SCENE_OPTIMIZER" value="true" />
+<local name="SUPPORT_SCENE_OPTIMIZER" value="false" />
-<local name="SUPPORT_PHOTO_NIGHT" value="true"/>
+<local name="SUPPORT_PHOTO_NIGHT" value="false"/>
```

These are **two separate knobs**, both off for the pilot. A later A/B can test one at a time to identify which, if either, contributes.

Everything else stays untouched: camera bridge, native HAL, photo resolutions, AE/AF controls, Video6 metadata, Face HAL, all radio and CP/EFS, kernel, VNDK.

**Hypothesis only:** Auto Scene Optimizer/Photo Night could schedule additional exposure frames. Another root cause could instead be autofocus or AE not converging, zero-shutter-lag disabled, unsupported OEM capture tags, synchronous JPEG queue or app-side saving.

## Reproducible evidence test on Zorin

Before flashing anything, try disabling `Scene optimizer` and automatic night settings inside Samsung Camera **if controls are exposed**. This is lower risk than installing a vendor image and may show whether the hypothesis is plausible.

Optional photo-save latency tool (takes 3 deliberate test photos, no photos read):
```bash
curl -fLsS "https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-shutter-lag-photo-fast-feature-gate/tools/alice_shutter_to_file_probe.py" -o ~/ALICE_SHUTTER_PROBE.py
python3 ~/ALICE_SHUTTER_PROBE.py --trials 3 --output ~/ALICE_SHUTTER_BASELINE.json
```
Keep Camera already open in Photo mode pointed at a well-lit nonprivate subject. Tool sends `adb shell input keyevent 27` with user permission, then observes **new filenames ONLY** in `/sdcard/DCIM/Camera`. It does not read photos. **Keyevent 27 might be ignored by a custom port.** Report explicitly measures *host keyevent to saved image*, not exact sensor shutter moment. If key ignored, cannot conclude anything from a null result.

If trial flashed after checking **real device vendor partition size and verified rollback** using original bootable Camera+Video6 vendor, repeat same benchmark in identical scene/lighting, preferably same photo mode, orientation, resolution, and flash setting. If lag unchanged, roll back and investigate capture pipeline rather than force further arbitrary photo flags.

## CI gates

`tools/test_shutter_feature_gate.py` compares EROFS input feature XML with the exact known-good baseline using XML nodes **and full bytes**, checks two and only two toggles. The existing Camera Video6/Face/RIL compatibility and EROFS reconstruction test workflow builds image as:

`vendor-a16-shutter-photo-gate-video6-UNTESTED.img`

Github Actions artifact name:
`ALICE-A16-SHUTTER-PHOTO-GATE-VIDEO6-UNTESTED-NO-FLASH`

No latency claim from CI. Face/Iris will be handled in a **separate** secure sensor integration branch; no fake biometrics or IR light manipulation.
