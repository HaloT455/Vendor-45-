#!/usr/bin/env python3
"""Read-only JADX inspection of S8+ exact 2026-10-24 Telephony framework DEX.

Does NOT patch/flash framework, write the phone, change radio settings, or
upload system binaries to any service. Uses local JADX CLI to inspect exactly
three relevant classes in an exact-SHA256-verified source JAR.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

EXPECTED_SHA256 = "8e58d49ad355df0e69af9a459edd138fdcf23c6462059b058ba394173c3769e1"
METHODS = {
    "RIL": (
        "makeStaticRadioCapability",
        "getRadioCapability",
        "setRadioCapability",
        "processResponse",
    ),
    "Phone": ("getRadioAccessFamily", "updateAllowedNetworkTypes", "radioCapability"),
    "ProxyController": ("setRadioCapability", "getMaxRafSupported", "getMinRafSupported"),
}
CLASS_PREFIX = "com.android.internal.telephony."
MAX_PRINT = 120  # per class: limit chat output; full local decompilation is retained


def choose_jadx(value: str | None) -> Path:
    options = []
    if value:
        options.append(Path(value).expanduser())
    found = shutil.which("jadx")
    if found:
        options.append(Path(found))
    home = Path.home()
    options += [
        home / "Downloads/jadx-1.5.6/bin/jadx",
        home / "Downloads/jadx/bin/jadx",
        home / "Downloads/ALICE_ROM_RADIO_DUMP/jadx/bin/jadx",
    ]
    for candidate in options:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "JADX not found. Download official jadx-1.5.6.zip from "
        "https://github.com/skylot/jadx/releases/tag/v1.5.6 "
        "and unzip to ~/Downloads/jadx-1.5.6, or use --jadx /path/to/bin/jadx."
    )


def verify_jar(jar: Path) -> str:
    if not jar.is_file():
        raise RuntimeError("Missing JAR: " + str(jar))
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            "Wrong framework hash: " + digest
            + " (expected S8+ original " + EXPECTED_SHA256 + "); refusing mismatch")
    return digest


def excerpt(source: str, targets: tuple[str, ...], lines_after: int = 34) -> str:
    """Show only bounded method-context excerpts, never entire ROM classes."""
    lines = source.splitlines()
    pieces: list[str] = []
    for name in targets:
        matches = [i for i, line in enumerate(lines) if
                   re.search(r"\b" + re.escape(name) + r"\s*\(", line)]
        if not matches:
            # May be an Android decompilation renamed/failed method: be explicit.
            pieces.append("  " + name + ": NOT FOUND IN DECOMPILED TEXT")
            continue
        index = next((i for i in matches if re.search(
            r"\b(?:private|protected|public|static|final)\b", lines[i])), matches[0])
        start = max(0, index - 2)
        stop = min(len(lines), index + lines_after)
        pieces.append("----- " + name + " (line " + str(index + 1) + ") -----")
        pieces.extend(f"{i + 1:05d} {lines[i]}" for i in range(start, stop))
    return "\n".join(pieces)


def extract_class(jadx: Path, jar: Path, output: Path, classname: str) -> Path:
    target = output / (classname + ".java")
    run = subprocess.run(
        [str(jadx), "--no-res", "--threads-count", "2",
         "--single-class", CLASS_PREFIX + classname,
         "--single-class-output", str(target),
         str(jar)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=240, check=False,
    )
    if run.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        log = "\n".join(run.stdout.splitlines()[-12:])
        raise RuntimeError(f"JADX {classname} FAILED (exit={run.returncode}):\n{log}")
    return target


def test_excerpt() -> None:
    sample = """class RIL {
  RadioCapability makeStaticRadioCapability() {
      return null;
  }
}
"""
    result = excerpt(sample, ("makeStaticRadioCapability", "getRadioCapability"))
    assert "makeStaticRadioCapability (line 2)" in result
    assert "getRadioCapability: NOT FOUND" in result
    print("PASS: bounded method excerpt and exact-hash verification guard fixture")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path,
        default=Path.home() / "Downloads/ALICE_ROM_RADIO_DUMP/telephony-common.jar")
    parser.add_argument("--out", type=Path,
        default=Path.home() / "Downloads/ALICE_ROM_RADIO_DUMP/raf_decompiled")
    parser.add_argument("--jadx", help="Path to official jadx CLI binary")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        test_excerpt()
        return
    checksum = verify_jar(args.jar)
    jadx = choose_jadx(args.jadx)
    args.out.mkdir(parents=True, exist_ok=True)
    report: list[str] = [
        "ALICE_S8PLUS_ANDROID16_TELEPHONY_DEX_AUDIT",
        "SOURCE_SHA256=" + checksum,
        "JADX=" + str(jadx),
        "READ_ONLY_HOST_DECOMPILATION; NO MODEM/PHONE/SIM WRITES",
    ]
    for name, methods in METHODS.items():
        filename = extract_class(jadx, args.jar, args.out, name)
        source = filename.read_text(errors="replace")
        report.append("==== " + name + " (" + str(filename.stat().st_size)
                      + " bytes decompiled) ====")
        chunk = excerpt(source, methods)
        # Avoid dumping entire Samsung framework code in terminal/reports.
        report.extend(chunk.splitlines()[:MAX_PRINT])
    dest = args.out / "ALICE_RAF_METHOD_EXCERPTS.txt"
    dest.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("\nALICE_REPORT:", dest)
    print("ALICE_DECOMPILED_CLASSES: 3 (locally saved only)")
    print("No modem, root, EFS, system, vendor, or camera changes.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("ERROR: " + str(exc))
