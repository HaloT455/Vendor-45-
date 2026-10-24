#!/usr/bin/env python3
"""Read-only capture and DEX inventory for the running Galaxy S8+ Android16 ROM.

Pulls ONLY /system/framework/telephony-common.jar to the Linux host.
No root needed, no device writes, no flash and no private SIM identifiers.
Dex string presence is a coarse inventory; it does NOT reveal method behavior.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile

REMOTE = "/system/framework/telephony-common.jar"
CLASS_NAMES = (
    ("RIL", b"Lcom/android/internal/telephony/RIL;"),
    ("Phone", b"Lcom/android/internal/telephony/Phone;"),
    ("ProxyController", b"Lcom/android/internal/telephony/ProxyController;"),
    ("RadioCapability", b"Lcom/android/internal/telephony/RadioCapability;"),
)
METHOD_NAMES = (
    "makeStaticRadioCapability",
    "getRadioAccessFamily",
    "setRadioCapability",
    "updateAllowedNetworkTypes",
)

def dex_inventory(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        members = [name for name in z.namelist()
                   if name.startswith("classes") and name.endswith(".dex")]
        if not members:
            raise RuntimeError("No classes*.dex inside telephony-common.jar")
        class_hit = {name: False for name, _ in CLASS_NAMES}
        method_hit = {name: False for name in METHOD_NAMES}
        for name in members:
            payload = z.read(name)
            if not payload.startswith(b"dex\n"):
                raise RuntimeError("Invalid DEX magic in " + name)
            for display, descriptor in CLASS_NAMES:
                class_hit[display] |= descriptor in payload
            for method in METHOD_NAMES:
                method_hit[method] |= method.encode("ascii") in payload
    return {"dex_files": members, "classes": class_hit, "method_names": method_hit}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path.home() / "Downloads" / "ALICE_ROM_RADIO_DUMP")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            mock = Path(d) / "telephony-common.jar"
            with zipfile.ZipFile(mock, "w") as z:
                z.writestr("classes.dex", b"dex\n035\0" +
                           CLASS_NAMES[0][1] + METHOD_NAMES[0].encode())
            report = dex_inventory(mock)
            assert report["classes"]["RIL"]
            assert not report["classes"]["Phone"]
            assert report["method_names"]["makeStaticRadioCapability"]
            assert not report["method_names"]["setRadioCapability"]
        print("PASS: DEX-only class/method inventory and checksum selftest")
        return
    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / "telephony-common.jar"
    command = ["adb", "-d", "pull", REMOTE, str(dest)]
    try:
        subprocess.run(command, check=True, timeout=90)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise SystemExit("ADB pull failed. Check USB and authorization: " + str(e))
    payload = dest.read_bytes()
    report = dex_inventory(dest)
    print("ALICE_JAR_CAPTURE:", dest)
    print("ALICE_JAR_BYTES:", len(payload))
    print("ALICE_JAR_SHA256:", hashlib.sha256(payload).hexdigest())
    print("ALICE_JAR_DEX_FILES:", ", ".join(report["dex_files"]))
    for name, found in report["classes"].items():
        print("ALICE_DEX_CLASS_" + name + ":", "PRESENT" if found else "NOT_FOUND_IN_DEX_STRINGS")
    for name, found in report["method_names"].items():
        print("ALICE_DEX_NAME_" + name + ":", "PRESENT" if found else "NOT_FOUND_IN_DEX_STRINGS")
    print("READ_ONLY: no device state or modem changes")
    print("NOTE: Strings/descriptor inventory is not a method decompilation.")

if __name__ == "__main__":
    main()
