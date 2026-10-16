#!/usr/bin/env python3
"""Assertions for P1 vendor config changes. No device access or firmware flash."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "metadata/vendor-image-manifest.json").read_text())
entries = {e["path"]: e for e in manifest["entries"]}
assert entries["etc/init"]["type"] == "directory"
assert entries["etc/init"]["mode"] == 0o755, "/vendor/etc/init mode must be 0755"
config = (root / "metadata/vendor_fs_config").read_text()
assert "vendor/etc/init 0 2000 0755\n" in config
assert "vendor/etc/init 0 2000 0000\n" not in config
rc = (root / "vendor/etc/init/alice-camera-test7.rc").read_text()
assert "property:ro.product.vendor.device=dream2lte" in rc
assert "property:ro.build.version.sdk=36" in rc
assert "property:ro.build.fingerprint=" not in rc
assert "mount none /vendor/etc/alice-test7/camera-feature.xml /system/cameradata/camera-feature.xml bind" in rc
assert (root / "vendor/etc/alice-test7/camera-feature.xml").is_file()
ril = (root / "vendor/etc/init/init.vendor.rilcommon.rc").read_text()
assert "setprop ro.telephony.default_network ${ro.vendor.sec.radio.def_network}" in ril
assert "setprop ro.telephony.default_network ${ro.vendor.radio.default_network}" not in ril
props = (root / "vendor/build.prop").read_text()
assert "ro.vendor.sec.radio.def_network=9\n" in props
print("PASS: Test7 init mode, camera mount trigger, RIL property wiring")
