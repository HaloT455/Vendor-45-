#!/usr/bin/env python3
"""ALICE S8+ Android16 LTE-per-slot compatibility A/B (ADB, no root needed).

Inspired by Redmi Note 5 Pro's MIUI Dual 4G policy work, NOT a transplant of
Qualcomm modem firmware. Only modifies Android USER allowed-network mask for
physical slot 0 when explicitly requested; never writes EFS/NV/CP/vendor
partitions, never changes slot 1, and restores original policy on failure.
Registration (PS in-service LTE) is mandatory for a successful outcome.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

LTE_BIT = 1 << 13
DEVICE = "dream2lte"
BACKUP = Path("ALICE_S8P_SIM1_LTE_POLICY_BACKUP.json")
SUPPORTED = re.compile(r"^[01]{8,63}$")
REG = re.compile(r"m(?:Voice|Data)RegState\s*=\s*(-?\d+)\s*\(")
STATE = re.compile(r"m(ServiceState|DataRegState|VoiceRegState)")


def adb(*arguments: str) -> str:
    p = subprocess.run(["adb", "-d", "shell", *arguments],
                       capture_output=True, text=True, timeout=25)
    if p.returncode:
        raise RuntimeError("ADB shell failed: " + (p.stderr.strip() or str(p.returncode)))
    return p.stdout.strip()


def prop(name: str) -> str:
    return adb("getprop", name).strip()


def read_mask(slot: int = 0) -> int:
    output = adb("cmd", "phone", "get-allowed-network-types-for-users", "-s", str(slot))
    candidates = [s.strip() for s in output.splitlines() if SUPPORTED.fullmatch(s.strip())]
    if len(candidates) != 1:
        raise RuntimeError("cmd phone did not return a recognized binary USER RAT mask: "
                           + repr(output[:150]))
    return int(candidates[0], 2)


def set_mask(value: int, slot: int = 0):
    if not (0 <= value < 2**63):
        raise ValueError("Invalid bitmask")
    response = adb("cmd", "phone", "set-allowed-network-types-for-users",
                   "-s", str(slot), format(value, "b"))
    if "completed" not in response.lower():
        raise RuntimeError("Telephony declined USER RAT update: " + response[:160])
    current = read_mask(slot)
    if current != value:
        raise RuntimeError("Readback USER mask disagrees with requested mask")


def service():
    # dumpsys alone cannot prove carrier assignment if active subscription mapping
    # changes; this diagnostic reports only the first service-state record.
    lines = [s for s in adb("dumpsys", "telephony.registry").splitlines()
             if "mServiceState=" in s]
    if not lines:
        return {"slot0_voice": "UNKNOWN", "slot0_data": "UNKNOWN"}
    a = lines[0]
    voice = re.search(r"mVoiceRegState\s*=\s*([01])\(", a)
    data = re.search(r"mDataRegState\s*=\s*([01])\(", a)
    return {"slot0_voice": "IN_SERVICE" if voice and voice.group(1) == "0" else "NOT_CONFIRMED",
            "slot0_data": "IN_SERVICE" if data and data.group(1) == "0" else "NOT_CONFIRMED"}


def check_device():
    dev = prop("ro.product.vendor.device")
    if dev != DEVICE:
        raise RuntimeError(f"Refusing non-{DEVICE} device: {dev!r}")
    if prop("persist.radio.multisim.config").lower() != "dsds":
        raise RuntimeError("DSDS not enabled; this A/B is specifically for paired two-SIM ROM")
    if prop("gsm.sim.state").split(",")[0].strip().upper() not in ("READY", "LOADED"):
        raise RuntimeError("Slot 0 SIM not ready")


def snapshot() -> dict:
    check_device()
    mask0 = read_mask(0)
    try:
        mask1 = read_mask(1)
    except RuntimeError:
        mask1 = None
    rat = prop("gsm.network.type").split(",")
    return {"device": DEVICE, "slot0_user_network_mask": format(mask0, "b"),
            "slot0_lte_allowed": bool(mask0 & LTE_BIT),
            "slot1_user_network_mask": format(mask1, "b") if mask1 is not None else None,
            "slot1_unchanged_by_tool": True,
            "slot0_reported_rat": rat[0].strip() if rat else "",
            "registration": service(),
            "sim_states": prop("gsm.sim.state"),
            "policy_only_not_modem_claim": True,
            "modem_efs_nv_cp_unmodified": True}


def store_backup(mask: int):
    if BACKUP.exists():
        existing = json.loads(BACKUP.read_text())
        if existing.get("device") != DEVICE:
            raise RuntimeError("Backup belongs to another device")
        raise RuntimeError("Existing backup found. Use --rollback before another --apply-slot1.")
    fd = BACKUP.open("x", encoding="utf-8")
    try:
        BACKUP.chmod(0o600)
        json.dump({"device": DEVICE, "slot": 0, "mask": format(mask, "b")}, fd)
        fd.write("\n")
    finally:
        fd.close()


def original_mask() -> int:
    record = json.loads(BACKUP.read_text())
    if record.get("device") != DEVICE or record.get("slot") != 0:
        raise RuntimeError("Invalid saved backup identity")
    mask = record.get("mask", "")
    if not SUPPORTED.fullmatch(mask):
        raise RuntimeError("Invalid saved mask")
    return int(mask, 2)


def rollback():
    check_device()
    value = original_mask()
    set_mask(value)
    print("ROLLBACK_OK: restored slot 0 USER mask; SIM2 was untouched")
    BACKUP.unlink()


def trial(wait_seconds: int):
    before = snapshot()
    print("BEFORE:", json.dumps(before, ensure_ascii=False))
    old = read_mask(0)
    if old & LTE_BIT:
        print("NO_POLICY_FIX_NEEDED: SIM1 LTE was ALREADY allowed by USER mask.")
        print("Investigate RIL/RadioCapability/CP registration; do not spoof dual LTE.")
        return
    store_backup(old)
    new = old | LTE_BIT
    print("ATTEMPT: add LTE bit to SIM1 USER allowed RAT, preserve all other bits.")
    applied = False
    try:
        set_mask(new)
        applied = True
        start = time.monotonic()
        while time.monotonic() - start < wait_seconds:
            r = snapshot()
            first = r["slot0_reported_rat"].upper()
            if first.startswith("LTE") and r["registration"]["slot0_data"] == "IN_SERVICE":
                print("LTE_PS_REGISTERED_OBSERVED:", json.dumps(r, ensure_ascii=False))
                print("WARNING: verify Viettel identity, actual data, calling and VoLTE.")
                print("To restore the original network mask: python3 "
                      + Path(__file__).name + " --rollback")
                return
            time.sleep(4)
        print("NO_LTE_PS_REGISTRATION: restoring original USER policy automatically.")
    finally:
        # Preserve backup if rollback cannot reach adb, allowing manual recovery.
        if BACKUP.exists():
            if applied:
                print("NOTE: if adb connection was lost, run --rollback manually.")
            rollback()


def selftest():
    for mask in (0, 1, (1 << 2) | (1 << 3) | (1 << 19)):
        assert ((mask | LTE_BIT) & ~LTE_BIT) == (mask & ~LTE_BIT)
        assert (mask | LTE_BIT) & LTE_BIT
        assert bool(mask & LTE_BIT) == bool(int(format(mask, "b"), 2) & LTE_BIT)
    assert SUPPORTED.fullmatch("01001111101111111111")
    assert not SUPPORTED.fullmatch("0102")
    assert (int("01000001000000000000", 2) & LTE_BIT) != 0
    print("PASS: LTE bitmask OR is non-destructive and parses AOSP shell binary masks.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apply-slot1", action="store_true", help="Opt-in LTE USER mask trial on physical SIM slot 1 (index 0), rollback on no PS LTE")
    g.add_argument("--rollback", action="store_true", help="Restore original SIM1 USER bitmask")
    g.add_argument("--selftest", action="store_true", help="No device needed")
    p.add_argument("--wait-seconds", type=int, default=32)
    args = p.parse_args()
    if args.selftest:
        selftest()
    elif args.rollback:
        rollback()
    elif args.apply_slot1:
        if not 8 <= args.wait_seconds <= 120:
            p.error("wait-seconds must be between 8 and 120")
        trial(args.wait_seconds)
    else:
        print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print("ERROR:", str(exc), file=sys.stderr)
        print("If an apply was interrupted, check for", BACKUP,
              "and use --rollback. No EFS/CP write was attempted.", file=sys.stderr)
        sys.exit(2)
