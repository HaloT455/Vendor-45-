# ALICE Test7 Camera/HAL – Dual LTE investigation (research only)

## Inputs and confirmed facts

Device: SM-G955F/FD (dream2lte / Exynos 8895), proprietary vendor Test7,
Android 16 / Samsung One UI port.

The 9 October runtime log confirmed `org.lineageos.aperture` was able to
create 1440x1080 PRIVATE preview and 3264x2448 JPEG capture streams through
the legacy Exynos camera HAL3 path. The framework emitted missing Samsung tag
lookups for `availablePictureStreamConfigurations` and
`availableFullPictureStreamConfigurations`, but it continued to
`ExynosCamera3Interface::configure_streams`; *that pair of log lines
alone is not proof of a fatal failure*. Do not fabricate descriptors with
arbitrary stream sizes or claim newer HAL features are implemented.

The modem/RIL log showed `responseRadioCapability: Invalid response` and
`RILJ: Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0` for
phone0/phone1. The Android telephony framework can subsequently reject
network mode requests due to RAF=0 before the CP sees them.

Prior CP_G955FXXUCDUD1 static examination found the modem path:
`Mode change to AUTO/LTE is not allowed since LTE is configured on other
stack` for BOTH stacks; this is beyond a cosmetic menu warning. Two HIDL
radio instances do not bypass that modem behavior.

## Required compatibility repair

Camera:
1. Resolve the exact Samsung Camera process crash/exit/preview log around
   app launch and identify the first failing call, not the first warning.
2. Verify Samsung provider@4.0 -> device@5.0 legacy bridge and device@3.3
   module ABI; compare 32/64 ELF DT_NEEDED against actual system image.
3. Inspect `get_vendor_tag_ops` and descriptor registration, and test actual
   JPEG/preview results. Any bridge must map real supported metadata and
   preserve underlying stream handling (including fences and buffer lifetime).
4. Rebuild an actual compatible bridge from source using Android 16 headers,
   with rollback and device tests; renaming HAL versions is not an upgrade.

Dual LTE:
1. Repair framework/RIL `getRadioCapability` and validate nonzero RAF for
   both phoneIds without inventing supported bands.
2. Confirm one SIM at a time can enter LTE role and hand it to the other.
3. To request LTE on both SIMs concurrently, CP must support dual LTE
   registration, RF scheduling and carrier combinations. Test CP behavior
   rather than deleting rejection strings or patching a boolean blindly.
4. Preserve IMEI, EFS/NV, carrier policy, baseband, and keep rollback.

No vendor binary, kernel, modem or framework JAR is modified by this
investigation. Native ABI probe produces `out/compat.json` from Test7.
A successful CI reports offline integrity only.
