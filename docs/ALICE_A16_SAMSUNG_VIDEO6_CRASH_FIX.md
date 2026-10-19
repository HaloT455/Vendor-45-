# ALICE Galaxy S8+ One UI8 / Android16 — Samsung video six-int crash fix

## Real device finding, 2026-10-20 05:50:46

User uploaded the read-only archive ALICE_POSTFLASH_CAMERA_20261020_055039.zip (the private archive stays off GitHub). It establishes that the earlier vendor from Actions #39287309454 **was flashed** and the following Samsung vendor tags were **registered**:
- `samsung.android.scaler.availablePreviewStreamConfigurations`
- `samsung.android.scaler.availablePictureStreamConfigurations`
- `samsung.android.scaler.availableVideoConfigurations`

Camera's system-key permission is already granted. The app continues past preview setup, then fails when creating a video recorder session with:
`java.lang.IllegalArgumentException: lower must be less than or equal to upper`.
The stack runs through `com.samsung.android.camera.core2.container.VideoStreamConfig`, `ScalerCapability`, `RecordingManagerImpl.getRecordingFpsRange`, and `PrepareVideoMakerRequest`.

The vendor camera service showed the synthetic video metadata as 4-int preview tuples, e.g. `[34,4032,3024,0]`. Samsung reads that as video configuration values, where `3024 > 0` invalidates the FPS Range. This is a **confirmed error in the previous ALICE bridge**.

## Cross-checked six-int Samsung HAL contract

Samsung Exynos HAL implementation:
https://github.com/Linux4/android_hardware_samsung_slsi-linaro_exynos/blob/lineage-21/libcamera3/common/Sec/ExynosCameraMetadataConverterVendor.cpp

Method `m_createVendorControlAvailableVideoConfigurations` encodes each item as SIX integers:
`[width, height, minimumFPS, maximumFPS, stabilizationCropPercent, recordingTimeLimit]`.
The reference divides the stored minimum/maximum FPS values by 1000 before publishing and appends crop ratio and time limit. An independently published Samsung Camera2 dump exhibits arrays divisible by 6 and valid FPS ranges. These data show why our previous 4-int records were invalid.

## Patch on work/a16-camera-video6-metadata-fix

- In `tools/native_camera/alice_preview_bridge.c`, replace `add(VIDEO_TAG,preview_config,preview_n*4)` with a real `video_config` containing SIX int32 values per size. Register all three tags without changing the existing valid preview and still photo handling.
- Derive candidate sizes exclusively from the actual per-camera AOSP `android.scaler.availableStreamConfigurations` implementation-defined outputs (format 34).
- Require AOSP `android.control.aeAvailableTargetFpsRanges` to contain fixed `[30,30]` and require each output's AOSP `android.scaler.availableMinFrameDurations` to be fast enough for 30fps.
- Conservative first trial: only sizes 640..1920 wide and 360..1080 high. Do not claim UHD/60fps, hardware codec negotiation, audio encoding or actual video capture.
- Use crop=0 and timeLimit=0 (no invented camera-specific stabilization crop or time limit) consistent with Exynos HAL's tuple fields.
- If genuine per-camera FPS/duration metadata is unavailable, abort augmentation rather than invent fake FPS.
- Preserve backup Exynos8895 camera HAL delegates in both 32/64 ABIs, DSDS `ro.telephony.default_network=9,9`, modem CP, EFS, radio blobs and `baseline/test7`.

## CI and runtime limitations

GitHub Actions builds a new, separate research EROFS and rechecks the six-int format and the two earlier preview NPE regression tests. CI success validates code generation, ABI and output integrity only. Real app open, recording 30fps and saved/playable video must be measured on the device after deliberate user testing. Prior experimental vendor image is definitively **not a fix for video**.

The phone has a validated previous vendor backup (629145600 bytes) and TWRP per user report; the exact recovery access was not exercised during this conversation. Do not claim flash-ready or a working recovery merely from disk bytes.
