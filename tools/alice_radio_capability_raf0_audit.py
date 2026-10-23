#!/usr/bin/env python3
"""S8+ Android16 RadioCapability RAF=0 root-cause audit. READ ONLY.

Designed for Samsung Exynos8895 dual SIM with proprietary RIL which returns
Invalid response to GET_RADIO_CAPABILITY. AOSP then uses framework-res
config_radio_access_family as static fallback. If effective overlay string
is missing/empty/malformed, that fallback stays RAF=0 and Android refuses
to update preferred network type. This test does not repair HAL/modem and
does not claim dual LTE capability.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

RAF_TOKENS = frozenset((
    "GPRS", "EDGE", "UMTS", "IS95A", "IS95B", "1XRTT", "EVDO_0",
    "EVDO_A", "HSDPA", "HSUPA", "HSPA", "EVDO_B", "EHRPD", "LTE",
    "HSPAP", "GSM", "TD_SCDMA", "HS", "CDMA", "EVDO", "WCDMA",
    "LTE_CA", "NR",
))
RADIO_EVENTS = {
    "radio_capability_hal_invalid": r"responseRadioCapability:\s*Invalid response",
    "fake_raf_zero": r"Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using\s+0\b",
    "raf_zero_preferred_network_aborted": r"setPreferredNetworkType:\s*Abort, unknown RAF:\s*0\b",
    "request_radio_capability": r"\bGET_RADIO_CAPABILITY\b",
    "radio_unavailable": r"\bRADIO_NOT_AVAILABLE\b",
}
NETWORK_TYPES = frozenset(("LTE", "LTE_CA", "4G", "4G+"))


def command(*args: str, limit: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["adb", "-d", "shell", *args],
            text=True, capture_output=True, timeout=limit, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (1, f"ADB_UNAVAILABLE:{type(exc).__name__}")
    return (proc.returncode, proc.stdout.strip() if proc.returncode == 0
            else "SHELL_COMMAND_UNAVAILABLE")


def classify_resource(raw: str, ok: bool) -> dict:
    if not ok:
        return {"state": "LOOKUP_UNAVAILABLE", "lte_token": None, "value": None}
    raw = raw.strip().strip('"').strip("'")
    if raw == "" or raw.lower() in ("null", "(null)", "none"):
        return {"state": "EMPTY", "lte_token": False, "value": raw}
    # Refuse verbose lookup text, error output, or data not described by
    # Android RadioAccessFamily.rafTypeFromString(); no guessing!
    values = [p.strip().upper() for p in raw.split("|")]
    if not values or any(x not in RAF_TOKENS for x in values):
        return {"state": "UNRECOGNIZED", "lte_token": None,
                "value": "NON_CANONICAL_RESOURCE"}
    return {"state": "VALID_WITH_LTE" if "LTE" in values or "LTE_CA" in values
            else "VALID_WITHOUT_LTE",
            "lte_token": "LTE" in values or "LTE_CA" in values,
            "value": "|".join(values)}


def service_state(dump: str) -> list[dict]:
    out = []
    for line in dump.splitlines():
        if "mServiceState=" not in line:
            continue
        voice = re.search(r"mVoiceRegState=([01])\(", line)
        data = re.search(r"mDataRegState=([01])\(", line)
        out.append({
            "phone_index_order_in_registry": len(out),
            "voice_in_service": voice.group(1) == "0" if voice else None,
            "data_in_service": data.group(1) == "0" if data else None,
            "radio_rat_not_confirmed_by_registration": True,
        })
        if len(out) == 2:
            break
    return out


def audit() -> dict:
    rc, device = command("getprop", "ro.product.vendor.device")
    if rc or device.strip() != "dream2lte":
        raise RuntimeError("This audit is only for the Galaxy S8+ dream2lte")
    resolutions = {}
    for key in ("0", "current"):
        rc, value = command("cmd", "overlay", "lookup", "--user", key,
                            "android", "android:string/config_radio_access_family")
        resolutions[key] = classify_resource(value, rc == 0)
    rc, overlays = command("cmd", "overlay", "list", "--user", "0")
    # Only count basic states; never store whole overlays list or private names.
    overlays_audit = {
        "query_succeeded": rc == 0,
        "android_target_overlay_entries": None,
    }
    if rc == 0:
        # This count is informational; the resource lookup is authoritative.
        block = overlays.split("android\n", 1)[-1].split("\n\n", 1)[0]
        overlays_audit["android_target_overlay_entries"] = sum(
            row.strip().startswith(("[X]", "[ ]", "---")) for row in block.splitlines()
        )
    rc, old = command("logcat", "-b", "radio", "-d", "-t", "6000")
    events = {name: (len(re.findall(pattern, old, re.I)) if rc == 0 else None)
              for name, pattern in RADIO_EVENTS.items()}
    rc, states = command("dumpsys", "telephony.registry")
    rc2, rats = command("getprop", "gsm.network.type")
    current_rat = rats.split(",")[:2] if rc2 == 0 else []
    result = {
        "device": device,
        "effective_framework_raf": resolutions,
        "framework_overlay_summary": overlays_audit,
        "radio_event_counts_in_buffer_only": events,
        "service_registration": service_state(states) if rc == 0 else [],
        "reported_rat_by_slot": [r.strip() for r in current_rat],
        "safe_next_step": (
            "If config_radio_access_family is EMPTY/UNRECOGNIZED, correct the "
            "Android framework-res overlay and verify a nonzero static RAF; "
            "the vendor RIL still returns an invalid RadioCapability response. "
            "If the resource is VALID_WITH_LTE, inspect framework-res caching, "
            "resources loaded by com.android.phone, and native RIL callback."
        ),
        "flash_ready": False,
        "confirms_dual_sim_simultaneous_lte": False,
        "writes_to_device": False,
        "modem_cp_efs_nv_imei_touched": False,
    }
    return result


def selftest():
    assert classify_resource("", True)["state"] == "EMPTY"
    assert classify_resource("GSM|WCDMA|LTE", True)["state"] == "VALID_WITH_LTE"
    assert classify_resource("GSM|CDMA|EVDO|WCDMA|LTE", True)["lte_token"]
    assert classify_resource("GSM|UMTS|4G+NOT_PARSED", True)["state"] == "UNRECOGNIZED"
    assert classify_resource("GSM|WCDMA", True)["state"] == "VALID_WITHOUT_LTE"
    assert classify_resource("", False)["state"] == "LOOKUP_UNAVAILABLE"
    assert len(service_state(
        "mServiceState=mVoiceRegState=1(OUT_OF_SERVICE),mDataRegState=1(OUT_OF_SERVICE)\n"
        "mServiceState=mVoiceRegState=0(IN_SERVICE),mDataRegState=1(OUT_OF_SERVICE)"
    )) == 2
    sample = (
        "RILC : responseRadioCapability: Invalid response\n"
        "RILJ : Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0\n"
        "Phone-0 : setPreferredNetworkType: Abort, unknown RAF: 0"
    )
    assert all(len(re.findall(p, sample, re.I)) == 1
               for k, p in RADIO_EVENTS.items()
               if k not in ("radio_unavailable", "request_radio_capability"))
    print("PASS: RAF resource parser, both-phone service flags, radio-buffer patterns")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.selftest:
        selftest()
        return
    info = audit()
    report = json.dumps(info, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print("DIAGNOSTIC_ERROR:", exc, file=sys.stderr)
        sys.exit(2)
