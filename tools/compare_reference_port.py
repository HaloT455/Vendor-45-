#!/usr/bin/env python3
"""Read-only SHA256 camera/RIL comparison: ALICE Test7 vs extracted vendor port."""
import argparse
import hashlib
import json
from pathlib import Path

PATTERNS = {
    "camera": [
        "lib*/hw/camera*.so", "lib*/libexynoscamera*.so",
        "lib*/libcamera*.so", "lib*/libshim*camera*.so",
        "lib*/vendor.samsung.hardware.camera*.so",
        "bin/hw/*camera*", "etc/init/*camera*.rc",
        "etc/vintf/manifest/*camera*.xml",
        "etc/permissions/*camera*.xml", "lib*/hw/gralloc*.so",
        "lib*/hw/hwcomposer*.so",
    ],
    "radio": [
        "bin/hw/*ril*", "bin/cbd", "lib*/libril*.so",
        "lib*/libsec-ril*.so", "lib*/vendor.samsung.hardware.radio*.so",
        "etc/init/*ril*.rc", "etc/init/*radio*.rc",
        "etc/init/init.baseband.rc", "etc/vintf/manifest/*radio*.xml",
        "etc/vintf/manifest/*seh*.xml",
    ],
}


def sha256(file):
    h = hashlib.sha256()
    with file.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root, category):
    result = {}
    for pattern in PATTERNS[category]:
        for p in root.glob(pattern):
            if p.is_file() and not p.is_symlink():
                result[p.relative_to(root).as_posix()] = {
                    "bytes": p.stat().st_size,
                    "sha256": sha256(p)
                }
    return result


def compare(current, reference, category):
    a, b = inventory(current, category), inventory(reference, category)
    diff = []
    common = set(a) & set(b)
    for path in sorted(set(a) | set(b)):
        if a.get(path) == b.get(path):
            continue
        diff.append({
            "file": path,
            "status": "different" if path in common else
                      "only_test7" if path in a else "only_reference",
            "test7": a.get(path),
            "reference": b.get(path),
        })
    return {
        "test7_files": len(a),
        "reference_files": len(b),
        "identical_files": len(common) -
            len([x for x in diff if x["status"] == "different"]),
        "differences": diff,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True,
                        help="extracted reference /vendor directory")
    parser.add_argument("--current", type=Path,
                        default=Path(__file__).resolve().parents[1] / "vendor")
    parser.add_argument("--output", type=Path, default=Path("out/port-diff.json"))
    args = parser.parse_args()
    if not args.current.is_dir() or not args.reference.is_dir():
        parser.error("Both directories must contain extracted vendor files")
    data = {
        "purpose": "offline comparison only",
        "flash_ready": False,
        "camera_hal_upgraded": False,
        "dual_lte_proven": False,
        "camera": compare(args.current, args.reference, "camera"),
        "radio": compare(args.current, args.reference, "radio"),
        "warning": "Do not transplant blobs or modify CP/EFS/NV automatically"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print("Camera differences:", len(data["camera"]["differences"]))
    print("Radio differences:", len(data["radio"]["differences"]))
    print("Report:", args.output)


if __name__ == "__main__":
    main()
