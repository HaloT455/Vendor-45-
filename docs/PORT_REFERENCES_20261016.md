# ALICE: external Camera/RIL port references (16 October 2026)

## 1. Best match: hlong UN1GAGA 1.1.0 for Exynos 8895

- Developer: hlong. Post: https://t.me/hlongupdates/207
- Dated 14 October 2026, build reference cc037466.
- Devices: Galaxy S8 dreamlte, S8+ dream2lte, Note8 greatlte.
- Built on UN1CA 3.2.1 / One UI 8.
- Changelog explicitly claims: Fix Camera on S8/S8+.
- Download URL: https://gofile.io/d/aHSMun0r ; password stated by author: unigaga.
- The July 2026 1.0.1 predecessor said S8/S8+ camera broken:
  https://t.me/s/hlongupdates?before=203

CAUTION: Nothing in this release announcement proves the proprietary
Samsung Camera app works, or that any HAL major version was upgraded.
The developer's 2025 post explicitly says the S8 Samsung Camera
relied on HAL1 features; legacy HAL3 lacks some 4K/60fps features:
https://t.me/s/hlongupdates?before=165

Compare extracted 1.0.1 vs 1.1.0 vendor files, and compare 1.1.0 against
our Test7. Candidate causes: camera blob / gralloc / provider /
manifest / init / SELinux / framework camera-app compatibility.
Never copy an arbitrary full vendor or flash another project's image.

## 2. Exynos8895 C++ camera wrapper source

https://github.com/exynos8895/android_device_samsung_universal8895-common/tree/lineage-18.1/hardware/camera

CameraWrapper.cpp exports HAL_MODULE_INFO_SYM and delegates
camera_get_vendor_tag_ops to the original vendor module.
Camera3Wrapper.cpp wraps camera3_device_ops_t and forwards
configure_streams and process_capture_request. Android.bp contains
the necessary AOSP build dependencies.

This is genuine Camera2/Camera3 adapter source and is useful as an
ABI reference, but it targets an older LineageOS stack. It cannot
be dropped into Samsung's @4.0 provider and @5.0 session without
reworking and compiling for the actual One UI 8 framework.

## 3. Same-chipset alternative: Ivan Meler

https://ivanmeler.github.io/devices/dream2lte.html

LineageOS S8+ camera solutions are useful controls for native
Exynos 8895 operation. They do not establish Samsung OEM camera
compatibility with One UI 8.

## 4. Dual SIM 4G constraints

Samsung Galaxy S8 dual VoLTE issue:
https://r2.community.samsung.com/t5/Galaxy-S/S8-dual-sim-problem/m-p/3220425

Existing ALICE logs: both PHONE0/PHONE1 returned RadioAccessFamily=0;
modem G955FXXUCDUD1 includes an LTE-other-stack refusal path.
No located port has verified two simultaneous LTE registrations on
this hardware. Restore SIM1 or SIM2 LTE role switching first, then
test actual CP capabilities. Do not invent dual-active LTE via VINTF,
property, RIL fake response, or edit CP/EFS/NV.

## Safe diff of extracted ROMs

Once a reference /vendor filesystem is extracted:

    python3 tools/compare_reference_port.py \
      --reference /tmp/un1gaga/vendor \
      --output out/un1gaga-vs-test7.json

The tool records SHA256 of camera / RIL candidate files.
It does not automatically port any binary or generate a flash image.
Keep baseline/test7 immutable. Changes belong to work/camera-sim.
