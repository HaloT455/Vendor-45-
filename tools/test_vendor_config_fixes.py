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
# Experimental reference-recovery branch only: replicate the exact init rc that
# the user's SIM-working vendor.new.dat.br contains. A late ro property write
# may be rejected if already frozen on Android 16; CI does not prove runtime.
import hashlib
assert hashlib.sha256(ril.encode()).hexdigest() == "c61001ec4a485b436c99fb2d55786aabd92d6fc9f5e4b1b9beff458eb31be610", "RIL init differs from reference working vendor"
assert ril.count("setprop ro.telephony.default_network ${ro.vendor.radio.default_network}") == 1
props = (root / "vendor/build.prop").read_text()
assert "ro.vendor.sec.radio.def_network=9\n" in props
assert props.count("ro.telephony.default_network=9,9\n") == 1, "Android 16 DSDS requires per-phone default list"
print("PASS: Test7 init mode, camera mount, 9,9 early property, source-matched legacy RIL init; NOT device-verified")
