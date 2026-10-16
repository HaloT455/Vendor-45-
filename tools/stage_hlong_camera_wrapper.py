#!/usr/bin/env python3
"""Stage a pinned upstream Exynos8895 camera wrapper; NEVER build a flash ROM.

Copies original ALICE camera HAL to camera.vendor.universal8895.so and
places upstream hlong wrapper at camera.universal8895.so in a staging
directory only. Does not modify the vendor tree, EROFS metadata or device.
"""
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "5b73038bc943d8b8d3d0d6ef83588eea5a87b63c"
UPSTREAM_PREFIX = ("platform/exynos8895/patches/abvendor/vendor")
EXPECTED = {
    "lib": {
        "original": "9752d2976103edbf7855530ce9fae717bbe4df39",
        "wrapper": "c3e756812b8d2ab0574321927a47fd59612d7d13",
        "class": 1,
    },
    "lib64": {
        "original": "72e9846c6aec469960f89e4d86850939aab0daeb",
        "wrapper": "3e6bfbfa94fd5f23d5877a882dc49b7b8b98da50",
        "class": 2,
    },
}


def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def check(content: bytes, exp: str, elf_class: int, label: str) -> None:
    got = git_blob_sha(content)
    if got != exp:
        raise ValueError(f"{label}: source hash mismatch {got} != {exp}")
    if len(content) < 16 or content[:4] != b"\x7fELF" or content[4] != elf_class:
        raise ValueError(f"{label}: invalid ELF class or magic")


def download_wrapper(abi: str) -> bytes:
    source = f"{UPSTREAM_PREFIX}/{abi}/hw/camera.universal8895.so"
    url = f"https://raw.githubusercontent.com/nhglong/UN1GAGA/{UPSTREAM_COMMIT}/{source}"
    req = urllib.request.Request(url, headers={"User-Agent": "ALICE-camera-research/1.0"})
    with urllib.request.urlopen(req, timeout=40) as response:
        content = response.read(512 * 1024)
    return content


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=Path("out/stage_hlong_camera"))
    args = ap.parse_args()
    report = {
        "upstream": "https://github.com/nhglong/UN1GAGA",
        "commit": UPSTREAM_COMMIT,
        "target": "dream2lte",
        "flash_ready": False,
        "runtime_tested": False,
        "camera_fixed": False,
        "files": [],
        "warning": "Staging files have no vendor metadata/init integration or rollback installer",
    }
    payloads = []
    # Validate everything BEFORE writing even one output file.
    for abi, expected in EXPECTED.items():
        original_path = ROOT / "vendor" / abi / "hw" / "camera.universal8895.so"
        original = original_path.read_bytes()
        check(original, expected["original"], expected["class"], "original " + abi)
        wrapper = download_wrapper(abi)
        check(wrapper, expected["wrapper"], expected["class"], "wrapper " + abi)
        payloads += [
            (f"vendor/{abi}/hw/camera.vendor.universal8895.so", original, "original"),
            (f"vendor/{abi}/hw/camera.universal8895.so", wrapper, "upstream_wrapper"),
        ]
    dest = args.output
    for rel, content, role in payloads:
        output = dest / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        report["files"].append({
            "file": rel, "role": role, "bytes": len(content),
            "git_blob_sha1": git_blob_sha(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    (dest / "PROTOTYPE_NOT_FLASH_READY.txt").write_text(
        "Do not flash or install. Offline source-verified port stage only.\n"
        "Missing complete filesystem metadata, loader compatibility and physical testing.\n"
    )
    (dest / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"staged_files": len(report["files"]), "output": str(dest),
                      "flash_ready": False, "upstream_commit": UPSTREAM_COMMIT}))


if __name__ == "__main__":
    main()
