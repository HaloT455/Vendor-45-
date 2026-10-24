#!/usr/bin/env python3
"""ALICE S8+ SIM2 LTE handoff audit (read-only, privacy-filtered).

Run once after selecting SIM1 as mobile-data default, and once after manually
selecting SIM2 in Android Settings. Compares *observed* RAT, not capability masks.
NEVER changes modem CP, EFS, NV, SIM settings, preferred-network values, or
data-subscription selection. Raw phone dumps/logcat remain in process memory.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ALLOWED_PROPS = (
    "ro.product.vendor.device",
    "ro.telephony.default_network",
    "ro.vendor.radio.default_network",
    "persist.radio.multisim.config",
    "ro.vendor.multisim.simslotcount",
    "gsm.sim.state",
    "gsm.network.type",
    "gsm.data.network.type",
    "gsm.voice.network.type",
)
LTE = {"LTE", "LTE_CA", "LTE+", "4G", "4G+"}
LEGACY_3G = {"UMTS", "HSPA", "HSPA+", "HSUPA", "HSDPA", "HSPAP", "TD-SCDMA"}
NETWORK_ERROR_MARKERS = {
    "unknown_raf_zero": r"setPreferredNetworkType:\s*Abort,\s*unknown RAF:\s*0\b",
    "lte_other_stack": r"LTE is configured on other stack",
    "radio_not_available": r"\bRADIO_NOT_AVAILABLE\b",
    "preferred_modem_reject": r"setPreferredDataModem.{0,120}(?:REQUEST_NOT_SUPPORTED|GENERIC_FAILURE|INVALID_ARGUMENTS)",
}

def shell(*args: str) -> str:
    # No shell=True; prevent interpolation of untrusted output/args.
    try:
        p = subprocess.run(["adb", "-d", "shell", *args], capture_output=True,
                           text=True, timeout=20, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("ADB missing, unauthorized, or timed out") from exc
    if p.returncode != 0:
        raise RuntimeError("ADB command failed (check cable/authorization)")
    return p.stdout

def parse_phone_id(isub: str) -> int | None:
    """Resolve actual subId -> physical phoneId; never confuse subId with slot."""
    default = re.search(r"\bdefaultDataSubId\s*=\s*(-?\d+)", isub)
    slots = {}
    for m in re.finditer(r"Logical SIM slot\s+([01])\s*:\s*subId\s*=\s*(-?\d+)", isub):
        slots[int(m.group(2))] = int(m.group(1))
    if default:
        return slots.get(int(default.group(1)))
    # Fallback for platforms that expose the data phone ID directly.
    for pattern in (
        r"\b(?:mDefaultDataPhoneId|defaultDataPhoneId)\s*[:=]\s*(-?\d+)",
        r"\b(?:mDefaultDataPhoneId|defaultDataPhoneId)\s+(-?\d+)",
    ):
        m = re.search(pattern, isub, re.I)
        if m:
            value = int(m.group(1))
            return value if value in (0, 1) else None
    return None


def sub_state(isub: str) -> dict:
    """Expose only public slot/sub mapping and current data subscription IDs."""
    slots = {}
    for m in re.finditer(r"Logical SIM slot\s+([01])\s*:\s*subId\s*=\s*(-?\d+)", isub):
        slots[str(int(m.group(1)))] = int(m.group(2))
    def get(key: str) -> int | None:
        m = re.search(r"\b" + key + r"\s*=\s*(-?\d+)", isub)
        return int(m.group(1)) if m else None
    return {"slot_to_sub_id": slots,
            "default_data_sub_id": get("defaultDataSubId"),
            "active_data_sub_id": get("activeDataSubId")}


def parse_wwan_registration(registry: str) -> list[dict]:
    """Parse WWAN network registrations, not misleading gsm.network.type/IWLAN."""
    lines = [line for line in registry.splitlines() if "mServiceState=" in line][:2]
    out = []
    for phone_id in (0, 1):
        domains = {}
        if phone_id < len(lines):
            for record in re.findall(r"NetworkRegistrationInfo\{([^{}]*)", lines[phone_id]):
                # Explicitly EXCLUDE PS WLAN/IWLAN; it is not cellular LTE attach.
                transport = re.search(r"\btransportType=([A-Z_]+)", record)
                domain = re.search(r"\bdomain=(CS|PS)\b", record)
                state = re.search(r"\bregistrationState=([A-Z_]+)", record)
                rat = re.search(r"\baccessNetworkTechnology=([A-Z0-9_+]+)", record)
                if not (transport and transport.group(1) == "WWAN" and domain):
                    continue
                domains[domain.group(1)] = {
                    "registration": state.group(1) if state else "UNKNOWN",
                    "rat": rat.group(1) if rat else "UNKNOWN"}
        ps = domains.get("PS", {})
        out.append({
            "phone_id": phone_id,
            "cs_wwan": domains.get("CS", {"registration":"UNKNOWN", "rat":"UNKNOWN"}),
            "ps_wwan": domains.get("PS", {"registration":"UNKNOWN", "rat":"UNKNOWN"}),
            "ps_lte_registered": ps.get("rat") in LTE and
                ps.get("registration") in ("HOME", "ROAMING")
        })
    return out


def parse_rat(value: str) -> list[str]:
    return [re.sub(r"\s+", "", s).upper() for s in value.split(",")[:2]]

def rat_type(s: str | None) -> str:
    if not s:
        return "UNKNOWN"
    if s in LTE or s.startswith("LTE"):
        return "LTE_REPORTED"
    if s in LEGACY_3G:
        return "3G_REPORTED"
    if s in {"GPRS", "EDGE", "GSM", "CDMA", "1XRTT"}:
        return "2G_REPORTED"
    return "OTHER"

def take_snapshot(label: str) -> dict:
    props = {name: shell("getprop", name).strip() for name in ALLOWED_PROPS}
    isub = shell("dumpsys", "isub")
    default_phone = parse_phone_id(isub)
    registration = parse_wwan_registration(shell("dumpsys", "telephony.registry"))
    # Read buffered radio logs solely for pre-defined error counters, NEVER save raw lines.
    try:
        radio_log = shell("logcat", "-b", "radio", "-d", "-t", "350")
        log_counts = {name: len(re.findall(pattern, radio_log, re.I))
                      for name, pattern in NETWORK_ERROR_MARKERS.items()}
    except RuntimeError:
        log_counts = {name: None for name in NETWORK_ERROR_MARKERS}
    rats = parse_rat(props["gsm.network.type"])
    return {
        "schema": 1,
        "label_manual_only": label,
        "default_data_phone_id_verified": default_phone,
        "subscription_mapping": sub_state(isub),
        "wwan_registration": registration,
        "properties": props,
        "slots": [
            {"phone_id": i, "reported_rat": rats[i] if i < len(rats) else "UNKNOWN",
             "rat_class": rat_type(rats[i]) if i < len(rats) else "UNKNOWN"}
            for i in (0, 1)
        ],
        "filtered_radio_event_counts_historical": log_counts,
        "raw_logs_written": False,
        "lte_registration_confirmed_by_getprop_alone": False,
        "wwan_ps_both_lte_registered": all(x["ps_lte_registered"] for x in registration),
        "camera_vendor_modified": False,
        "efs_or_modem_modified": False,
    }

def dual_lte_check(snapshot: dict) -> dict:
    """Report whether BOTH current RAT indicators read LTE, never fabricate WWAN registration."""
    slots = {s["phone_id"]: s.get("rat_class") for s in snapshot.get("slots", [])}
    sim_states = snapshot.get("properties", {}).get("gsm.sim.state", "").split(",")
    both_loaded = len(sim_states) >= 2 and all(x.strip().upper() in
                       {"LOADED", "READY"} for x in sim_states[:2])
    both_lte = (slots.get(0) == "LTE_REPORTED" and slots.get(1) == "LTE_REPORTED")
    return {
        "candidate_both_lte_rat": bool(both_lte and both_loaded),
        "slot0_reported_rat": slots.get(0, "UNKNOWN"),
        "slot1_reported_rat": slots.get(1, "UNKNOWN"),
        "both_sim_states_ready": both_loaded,
        "independent_wwan_ps_home_lte_verified": False,
        "simultaneous_4g_service_proven": False,
        "result": ("BOTH_LTE_RAT_REPORTED_NEEDS_WWAN_CONFIRMATION"
                   if both_lte and both_loaded else
                   "BOTH_LTE_NOT_OBSERVED_OR_INCONCLUSIVE"),
        "requires": "Two independently verified WWAN PS HOME LTE registrations on phoneId0 and phoneId1",
        "modem_or_efs_written": False,
    }


def compare(sim1: dict, sim2: dict) -> dict:
    a, b = sim1["default_data_phone_id_verified"], sim2["default_data_phone_id_verified"]
    before = {x["phone_id"]: x["rat_class"] for x in sim1["slots"]}
    after = {x["phone_id"]: x["rat_class"] for x in sim2["slots"]}
    if a != 0 or b != 1:
        conclusion = "DATA_SWITCH_NOT_CONFIRMED"
        next_check = "Confirm Settings > SIM manager > Mobile data switched SIM1 to SIM2, then recapture."
    elif before.get(0) == "LTE_REPORTED" and after.get(1) == "LTE_REPORTED":
        conclusion = "LTE_ROLE_HANDOFF_REPORTED"
        next_check = "Verify LTE WWAN service registration, calls and data; getprop RAT alone is not proof."
    elif before.get(0) == "LTE_REPORTED" and after.get(1) != "LTE_REPORTED":
        conclusion = "SIM2_LTE_HANDOFF_NOT_OBSERVED"
        next_check = ("Test SIM2 alone with SIM1 absent, network selection and live RadioCapability/RAF "
                      "callback; no safe boot/vendor radio patch identified yet.")
    else:
        conclusion = "NOT_ENOUGH_BASELINE_EVIDENCE"
        next_check = "First establish SIM1 LTE with the reference boot/vendor and capture a fresh snapshot."
    return {
        "status": conclusion,
        "default_data_phone_id_before": a,
        "default_data_phone_id_after": b,
        "slot0_rat_before_after": [before.get(0), after.get(0)],
        "slot1_rat_before_after": [before.get(1), after.get(1)],
        "next_check": next_check,
        "simultaneous_dual_lte_proven": False,
        "no_firmware_changes": True,
    }

def selftest() -> None:
    assert parse_phone_id(" defaultDataPhoneId=1 ") == 1
    owner_isub = ("  Logical SIM slot 0: subId=1\n"
                  "  Logical SIM slot 1: subId=2\n"
                  "defaultDataSubId=1\nactiveDataSubId=1")
    assert parse_phone_id(owner_isub) == 0
    assert sub_state(owner_isub)["slot_to_sub_id"] == {"0": 1, "1": 2}
    assert sub_state(owner_isub)["active_data_sub_id"] == 1
    switched = owner_isub.replace("defaultDataSubId=1", "defaultDataSubId=2")
    assert parse_phone_id(switched) == 1
    reg = (
      "mServiceState=NetworkRegistrationInfo{ domain=CS transportType=WWAN "
      "registrationState=HOME accessNetworkTechnology=LTE},"
      "NetworkRegistrationInfo{ domain=PS transportType=WWAN "
      "registrationState=HOME accessNetworkTechnology=LTE}\n"
      "mServiceState=NetworkRegistrationInfo{ domain=PS transportType=WLAN "
      "registrationState=HOME accessNetworkTechnology=IWLAN},"
      "NetworkRegistrationInfo{ domain=PS transportType=WWAN "
      "registrationState=NOT_REG_OR_SEARCHING accessNetworkTechnology=UMTS},"
      "NetworkRegistrationInfo{ domain=CS transportType=WWAN "
      "registrationState=HOME accessNetworkTechnology=UMTS}")
    ww = parse_wwan_registration(reg)
    assert ww[0]["ps_lte_registered"]
    assert not ww[1]["ps_lte_registered"]
    assert ww[1]["ps_wwan"]["rat"] == "UMTS"
    assert parse_phone_id("mDefaultDataPhoneId: 0") == 0
    assert parse_phone_id("subscriberId=555111") is None
    assert rat_type("HSPA+") == "3G_REPORTED"
    assert rat_type("LTE") == "LTE_REPORTED"
    a = {"default_data_phone_id_verified": 0,
         "slots": [{"phone_id": 0, "rat_class": "LTE_REPORTED"},
                   {"phone_id": 1, "rat_class": "3G_REPORTED"}]}
    b = {"default_data_phone_id_verified": 1,
         "slots": [{"phone_id": 0, "rat_class": "3G_REPORTED"},
                   {"phone_id": 1, "rat_class": "LTE_REPORTED"}]}
    assert compare(a, b)["status"] == "LTE_ROLE_HANDOFF_REPORTED"
    two = {"properties": {"gsm.sim.state": "LOADED,LOADED"}, "slots":
           [{"phone_id": 0, "rat_class": "LTE_REPORTED"},
            {"phone_id": 1, "rat_class": "LTE_REPORTED"}]}
    assert dual_lte_check(two)["candidate_both_lte_rat"]
    assert not dual_lte_check(two)["simultaneous_4g_service_proven"]
    two["slots"][1]["rat_class"] = "3G_REPORTED"
    assert not dual_lte_check(two)["candidate_both_lte_rat"]
    b["slots"][1]["rat_class"] = "3G_REPORTED"
    assert compare(a, b)["status"] == "SIM2_LTE_HANDOFF_NOT_OBSERVED"
    b["default_data_phone_id_verified"] = None
    assert compare(a, b)["status"] == "DATA_SWITCH_NOT_CONFIRMED"
    print("PASS: real S8+ subId to slot mapping, WWAN-only PS/CS registration and LTE handoff fixtures")

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot", choices=["sim1", "sim2"])
    g.add_argument("--compare", nargs=2, metavar=("SIM1_JSON", "SIM2_JSON"))
    g.add_argument("--dualcheck", action="store_true", help="read-only simultaneous dual LTE candidate gate")
    g.add_argument("--selftest", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.selftest:
        selftest()
        return
    if args.compare:
        a = json.loads(Path(args.compare[0]).read_text())
        b = json.loads(Path(args.compare[1]).read_text())
        result = compare(a, b)
    elif args.dualcheck:
        result = dual_lte_check(take_snapshot("simultaneous_candidate_read_only"))
    else:
        result = take_snapshot(args.snapshot)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output)

if __name__ == "__main__":
    main()
