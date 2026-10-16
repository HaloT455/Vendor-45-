#!/usr/bin/env python3
"""Prepare an isolated UN1GAGA Camera HAL wrapper EROFS trial (NO FLASH).

Only modifies an ephemeral GitHub Actions checkout, never the pinned
baseline/test7 branch. The manifest is updated in the runner so the EROFS
builder checks the actual original HAL bytes, metadata and added paths.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

from stage_hlong_camera_wrapper import EXPECTED, git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "metadata/vendor-image-manifest.json"
FS_CONFIG = ROOT / "metadata/vendor_fs_config"
FILE_CONTEXTS = ROOT / "metadata/vendor_file_contexts"
ORIG = "camera.universal8895.so"
BACKUP = "camera.vendor.universal8895.so"
EXPECTED_CONTEXT = "u:object_r:vendor_file:s0"


def check_elf(data: bytes, kind: int, label: str) -> None:
    if data[:4] != b"\x7fELF" or data[4] != kind:
        raise ValueError(f"Incorrect ELF magic/class: {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, default=ROOT / "out/stage_hlong_camera")
    parser.add_argument("--report", type=Path, default=ROOT / "out/camera-integration-trial.json")
    args = parser.parse_args()
    j = json.loads(MANIFEST.read_text())
    entries = {e["path"]: e for e in j["entries"]}
    meta = []
    staging = []
    for abi, expected in EXPECTED.items():
        original_path = f"{abi}/hw/{ORIG}"
        renamed_path = f"{abi}/hw/{BACKUP}"
        item = entries.get(original_path)
        assert item and item["type"] == "file" and item["nlink"] == 1, original_path
        assert renamed_path not in entries, "Backup camera HAL already exists"
        cur = (ROOT / "vendor" / original_path).read_bytes()
        reference_backup = (args.stage / "vendor" / renamed_path).read_bytes()
        wrapper = (args.stage / "vendor" / original_path).read_bytes()
        check_elf(cur, expected["class"], "original " + abi)
        check_elf(wrapper, expected["class"], "wrapper " + abi)
        assert cur == reference_backup, "Upstream staging changed original HAL"
        assert git_blob_sha(cur) == expected["original"], "Original HAL Git SHA mismatch"
        assert git_blob_sha(wrapper) == expected["wrapper"], "Wrapper Git SHA mismatch"
        assert hashlib.sha256(cur).hexdigest() == item["sha256"], "Original HAL manifest SHA256 mismatch"
        context = base64.b64decode(item["xattrs"]["security.selinux"]).decode()
        assert context == EXPECTED_CONTEXT, f"Unexpected SELinux context: {original_path}: {context}"
        fs_entry = f"vendor/{original_path} 0 0 0644"
        assert fs_entry in FS_CONFIG.read_text(), "Missing original fs_config row: " + fs_entry
        file_context = f"/vendor/{abi}/hw/camera\\.universal8895\\.so {context}"
        assert file_context in FILE_CONTEXTS.read_text(), "Missing original SELinux row: " + file_context
        staging.append((original_path, renamed_path, cur, wrapper, item))
        meta.append({
            "abi": abi, "original_path": original_path, "backup_path": renamed_path,
            "original_sha256": item["sha256"],
            "wrapper_sha256": hashlib.sha256(wrapper).hexdigest(),
            "original_git_sha": expected["original"], "wrapper_git_sha": expected["wrapper"],
            "selinux": context,
        })

    # No modification at all until all original/staged blobs validate.
    next_nid = max(e["nid"] for e in j["entries"]) + 512
    for src, backup, old_bytes, wrapper, item in staging:
        new_entry = copy.deepcopy(item)
        new_entry["path"] = backup
        new_entry["nid"] = next_nid
        next_nid += 512
        j["entries"].append(new_entry)
        old = ROOT / "vendor" / src
        dst = ROOT / "vendor" / backup
        assert not dst.exists()
        dst.write_bytes(old_bytes)
        old.write_bytes(wrapper)
    j["entries"] = sorted(j["entries"], key=lambda e: e["path"])
    MANIFEST.write_text(json.dumps(j, indent=2, ensure_ascii=False) + "\n")
    fs_lines = []
    ctx_lines = []
    for x in meta:
        new_path = x["backup_path"]
        fs_lines.append(f"vendor/{new_path} 0 0 0644")
        escaped = new_path.replace(".", "\\.")
        ctx_lines.append(f"/vendor/{escaped} {EXPECTED_CONTEXT}")
    with FS_CONFIG.open("a") as f:
        f.write("\n".join(fs_lines) + "\n")
    with FILE_CONTEXTS.open("a") as f:
        f.write("\n".join(ctx_lines) + "\n")
    report = {
        "source_project": "nhglong/UN1GAGA",
        "source_commit": "5b73038bc943d8b8d3d0d6ef83588eea5a87b63c",
        "type": "experimental standalone EROFS for ABI research",
        "baseline_branch_edited": False,
        "runtime_tested": False,
        "samsung_camera_verified": False,
        "flash_ready": False,
        "files": meta,
        "note": "HAL module loader and Android SELinux policy not tested on physical S8+; no flashing",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"integrated_wrapper_paths": len(meta),
                      "manifest_entries": len(j["entries"]),
                      "flash_ready": False, "report": str(args.report)}))


if __name__ == "__main__":
    main()
