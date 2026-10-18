#!/usr/bin/env python3
"""Integrate a signed ALICE RAF RRO into a disposable vendor checkout.

This only supplies the AOSP static fallback for legacy GET_RADIO_CAPABILITY.
It does not enable simultaneous LTE, change supported modem bands or touch EFS.
Requires a separate work/* branch, and a research-only image. Do not flash.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "metadata/vendor-image-manifest.json"
FS_CONFIG = ROOT / "metadata/vendor_fs_config"
CONTEXTS = ROOT / "metadata/vendor_file_contexts"
APK_DIR = "overlay/ALICE-RadioRAF"
APK = APK_DIR + "/ALICE-RadioRAF.apk"


def integrate(input_apk: Path, report_path: Path) -> dict:
    current = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    if not current.startswith("work/dual-sim-lte-raf-trial"):
        raise RuntimeError("Refusing integration outside dedicated experimental branch")
    data = input_apk.read_bytes()
    if len(data) < 2000 or not data.startswith(b"PK\x03\x04"):
        raise ValueError("Input must be a nonempty compiled/signed APK")
    manifest = json.loads(MANIFEST.read_text())
    by_path = {entry["path"]: entry for entry in manifest["entries"]}
    if APK_DIR in by_path or APK in by_path:
        raise RuntimeError("Overlay already integrated")
    overlay_dir = by_path["overlay"]
    template_dir = by_path["overlay/ConnectivityOverlay"]
    template_apk = by_path["overlay/ConnectivityOverlay/ConnectivityOverlay.apk"]
    if template_dir["type"] != "directory" or template_apk["type"] != "file":
        raise RuntimeError("Unexpected base overlay directory or APK metadata")
    label = base64.b64decode(template_apk["xattrs"]["security.selinux"])
    if label != b"u:object_r:vendor_overlay_file:s0":
        raise RuntimeError("Unexpected vendor overlay SELinux file label")
    if base64.b64decode(template_dir["xattrs"]["security.selinux"]) != label:
        raise RuntimeError("Mismatched vendor overlay directory label")

    next_nid = max(entry["nid"] for entry in manifest["entries"]) + 2048
    new_dir = copy.deepcopy(template_dir)
    new_dir.update({"path": APK_DIR, "nid": next_nid, "nlink": 2})
    new_apk = copy.deepcopy(template_apk)
    new_apk.update({
        "path": APK, "nid": next_nid + 2048, "nlink": 1,
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest()
    })
    overlay_dir["nlink"] += 1
    dst_dir = ROOT / "vendor" / APK_DIR
    dst_dir.mkdir(parents=True, exist_ok=False)
    (ROOT / "vendor" / APK).write_bytes(data)
    manifest["entries"].extend([new_dir, new_apk])
    manifest["entries"].sort(key=lambda item: item["path"])
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    with FS_CONFIG.open("a") as stream:
        stream.write(f"vendor/{APK_DIR} {new_dir['uid']} {new_dir['gid']} {new_dir['mode']:04o}\n")
        stream.write(f"vendor/{APK} {new_apk['uid']} {new_apk['gid']} {new_apk['mode']:04o}\n")
    with CONTEXTS.open("a") as stream:
        stream.write(f"/vendor/{re.escape(APK_DIR)} u:object_r:vendor_overlay_file:s0\n")
        stream.write(f"/vendor/{re.escape(APK)} u:object_r:vendor_overlay_file:s0\n")
    report = {
        "branch": current,
        "source_apk": str(input_apk),
        "staged_apk": APK,
        "apk_sha256": hashlib.sha256(data).hexdigest(),
        "new_entry_count": len(manifest["entries"]),
        "radio_access_family_fallback": "GSM|WCDMA|LTE",
        "reason": "historical GET_RADIO_CAPABILITY RAF=0, subject to live recheck",
        "vendor_modem_changed": False,
        "efs_nv_imei_changed": False,
        "dual_lte_claim": False,
        "android16_framework_idmap_verified": False,
        "runtime_radio_attach_verified": False,
        "flash_ready": False
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("out/alice-raf-stage-report.json"))
    args = parser.parse_args()
    print(json.dumps(integrate(args.apk, args.report), indent=2))
