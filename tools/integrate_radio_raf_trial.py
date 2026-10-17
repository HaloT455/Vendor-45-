#!/usr/bin/env python3
"""Add trial RAF overlay to temporary Camera+RIL EROFS checkout only.

Expects tools/integrate_hlong_camera_trial.py has already created
the two original-HAL backup inodes. No direct changes to persistent branch.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / "metadata/vendor-image-manifest.json"
FS = ROOT / "metadata/vendor_fs_config"
FC = ROOT / "metadata/vendor_file_contexts"
NEW_DIR = "overlay/ALICE-RadioRAF"
NEW_APK = NEW_DIR + "/ALICE-RadioRAF.apk"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apk", type=Path, required=True)
    p.add_argument("--report", type=Path, default=Path("out/alice-radio-raf-trial.json"))
    a = p.parse_args()
    data = a.apk.read_bytes()
    if not data.startswith(b"PK\x03\x04") or len(data) < 2000:
        raise ValueError("Overlay output not a valid ZIP/APK archive")
    j = json.loads(M.read_text())
    entries = {e["path"]: e for e in j["entries"]}
    assert len(j["entries"]) == 1433, "UN1GAGA and ALICE preview bridge integration must have run first"
    assert NEW_DIR not in entries and NEW_APK not in entries, "Overlay already present"
    base_dir = entries["overlay/ConnectivityOverlay"]
    base_apk = entries["overlay/ConnectivityOverlay/ConnectivityOverlay.apk"]
    root_overlay = entries["overlay"]
    assert root_overlay["nlink"] == 6 and base_dir["nlink"] == 2
    assert base_dir["type"] == "directory" and base_apk["type"] == "file"
    label = base_apk["xattrs"]["security.selinux"]
    assert base_dir["xattrs"]["security.selinux"] == label
    assert base64.b64decode(label) == b"u:object_r:vendor_overlay_file:s0"

    nid = max(e["nid"] for e in j["entries"]) + 512
    new_dir = copy.deepcopy(base_dir)
    new_dir.update(path=NEW_DIR, nid=nid)
    new_apk = copy.deepcopy(base_apk)
    new_apk.update(path=NEW_APK, nid=nid + 512,
                   size=len(data), sha256=hashlib.sha256(data).hexdigest())
    root_overlay["nlink"] = 7
    j["entries"].extend((new_dir, new_apk))
    j["entries"].sort(key=lambda e: e["path"])
    (ROOT / "vendor" / NEW_DIR).mkdir(exist_ok=False)
    (ROOT / "vendor" / NEW_APK).write_bytes(data)
    M.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n")
    with FS.open("a") as f:
        f.write(f"vendor/{NEW_DIR} 0 2000 0755\n")
        f.write(f"vendor/{NEW_APK} 0 0 0644\n")
    with FC.open("a") as f:
        f.write(f"/vendor/{NEW_DIR.replace('.', chr(92)+'.')} u:object_r:vendor_overlay_file:s0\n")
        f.write(f"/vendor/{NEW_APK.replace('.', chr(92)+'.')} u:object_r:vendor_overlay_file:s0\n")
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps({
        "state": "offline experiment only",
        "input": str(a.apk), "path": NEW_APK, "sha256": new_apk["sha256"],
        "manifest_entries": len(j["entries"]), "static_radio_access_family": "GSM|WCDMA|LTE",
        "purpose": "Nonzero AOSP static RAF fallback for unsupported RIL_GET_RADIO_CAPABILITY",
        "rro_idmap_runtime_verified": False,
        "both_sim_lte_verified": False,
        "simultaneous_dual_lte_verified": False,
        "camera_runtime_verified": False,
        "modem_firmware_changed": False,
        "efs_changed": False,
        "flash_ready": False
    }, indent=2) + "\n")
    print(json.dumps({"vendor_entries": len(j["entries"]), "overlay_added": NEW_APK,
                      "flash_ready": False}))


if __name__ == "__main__":
    main()
