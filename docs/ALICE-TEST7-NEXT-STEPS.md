# ALICE Test7 work branch: camera + SIM 2/4G

Baseline: `baseline/test7` at `d5748652ddf1eb4cdc18d2f51cbbde8f6fd16170`.
All work takes place in `work/camera-sim`; original Test7 vendor binary is unchanged.

## Confirmed offline

- Vendor tree contains 32/64-bit `camera.universal8895.so`, Exynos camera3 libraries,
  a Samsung camera provider executable, radio RIL binaries and HAL declarations.
- Android radio HIDL declares `slot1` and `slot2` plus Samsung radio bridges.
- No vendor-only evidence of concurrent LTE on both SIMs, VoLTE or VoWiFi.
- Samsung Camera issue includes missing/unsupported metadata for preview/picture stream
  formats, based on earlier device tests; version-string editing is not a HAL upgrade.
- Test7 camera feature XML is bind-mounted only under a strict ROM fingerprint/SDK match.
- Baseline metadata has `/vendor/etc/init` permission mode 0000; preserve it in the
  source baseline and separately verify startup behavior on the real device.
- An EROFS filesystem image alone is not a boot image or a flash-ready ROM.

## CI pipeline

Push commits only to `work/*`. The GitHub workflow:

1. rejects any drift of `baseline/test7` from its immutable commit;
2. audits ELF headers/dependencies, VINTF declarations and properties;
3. downloads erofs-utils 1.8.6 and checks its SHA-256;
4. verifies the original manifest, rebuilds EROFS, checks hashes and metadata;
5. uploads `vendor.img`, `vendor.report.json` and `audit.json` as **research-only**
   artifacts; it never deploys or flashes a device.

A passing job means **offline build verified**, not functioning camera or Dual LTE.

## Evidence required before a hardware patch

- **Camera**: matching system/vendor build, Samsung Camera open/preview/capture logcat,
  CameraService getCharacteristics and availablePictureStreamConfigurations,
  session configuration error lines, relevant SELinux denials, provider crash/tombstone.
- **Radio**: `getRadioCapability`/`setRadioCapability` traces per phoneId, modem/RIL
  capability responses (earlier `REQUEST_NOT_SUPPORTED`), 4G registration separately
  and simultaneously, SIM card profile, carrier IMS provisioning and IMS registration.
- **Compatibility**: Android system-side telephony framework, Samsung camera extension
  framework, HAL ABI/vendor dependencies, original `vendor`/kernel limits.

Do not rename a HAL version or toggle `persist.radio` properties to claim hardware
support. Propose each real patch with a byte/content diff, rollback, and specific test.
