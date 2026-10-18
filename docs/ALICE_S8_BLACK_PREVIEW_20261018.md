# ALICE S8+ SamsungCamera 16.5.02.48 black-preview regression (2026-10-18)

## Evidence (from private user-provided ADB archive; not committed)

Phone boots the ALICE Exynos8895 native Samsung preview-tag bridge. The Android camera service now displays **10** vendor tags: the 9 stock tags plus 0x80030000 `samsung.android.scaler.availablePreviewStreamConfigurations`, with valid 32-bit int stream tuples for both rear and front. **This confirms the previous stage loads and registers.** A 1440×1080 preview SurfaceView is created successfully. The user screenshot captures the still-black camera window.

At 08:51:05.556 Android logs:

- `VendorTagDescriptor: Tag name 'availablePictureStreamConfigurations' does not exist.`
- `SemCameraCharacteristics: CameraCharacteristics.Key(samsung.android.scaler.availablePictureStreamConfigurations) is not supported`
- At 08:51:05.557 `Request: Exception: picture size is not supported - 4032x3024`
- The SamsungCamera `RequestQueue` immediately enters `SHUTDOWN`, and later `CONNECT_MAKER`, `ADD_PREVIEW_SURFACE`, and `START_PREVIEW` report `Invalid request for current state(SHUTDOWN)`.
- `dumpsys media.camera` at 08:51:18 shows `UNCONFIGURED`, zero output streams, no in-flight capture requests. There is no evidence here that the sensor or ISP itself fails.

The same device camera service advertises standard `android.scaler.availableStreamConfigurations`:
- Rear: `[33 4032 3024 OUTPUT]` (actual BLOB/JPEG source), and `[34 1440 1080 OUTPUT]` (actual preview).
- Front: `[33 3264 2448 OUTPUT]` and `[34 1440 1080 OUTPUT]`.
  
## Source patch

Add the second Samsung scanner vendor tag `samsung.android.scaler.availablePictureStreamConfigurations` with ID 0x80030001 to the existing camera module tag bridge. Keep both 32/64 HAL wrappers and all 9 original Samsung tags. For each actual camera, derive *only format 33 (HAL_PIXEL_FORMAT_BLOB) outputs* from Camera2 standard metadata to build int32 [33,width,height,0] records, retain the existing format 34 private preview outputs [34,width,height,0]. Fail closed if the source metadata is missing or malformed, if any legacy ID collision is detected, or if there are no genuine outputs.

This does **not** repair other missing Samsung vendor tags (`availableFeatures`, `afAvailableModes`, `aeAvailableModes`, `colorSpaceAvailableModes`, `lensDistortionCorrectionAvailableModes`, and `statisticsBeautyAvailableFaceDetectModes`). Some may be optional; future actual device logs determine which are fatal. Do **not** invent Samsung enum semantics or enable unsupported camera processing.

CI validates native cross-compilation for both 32/64 Android ABI and complete EROFS. It cannot confirm runtime success; the next acceptance gate is an on-device test showing:
- Both Samsung preview and picture vendor tags registered, and actual rear 4032×3024 and front 3264×2448 in camera characteristics;
- Samsung Camera `PrepareMakerRequest` completes without unsupported picture size;
- A real `START_PREVIEW`, configured output streams, increasing capture frame counters and a visible live image;
- Working photo save. Do not claim fixed/flash-safe before these checks.

## S9+ UN1CA alignment

Uses UN1CA S9+ strategy of preserving device-specific native HAL and matching Samsung metadata contracts. Does **not** copy Exynos9810 native machine-code patches to Exynos8895. This repair is in the vendor module, not a modified Samsung-signed application.
