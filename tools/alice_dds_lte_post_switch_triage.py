#!/usr/bin/env python3
"""Read-only S8+ post-DDS-switch LTE triage from sanitized ALICE snapshots.

No adb writes, no SIM switching, no modem/EFS/boot/vendor access. This tool
does NOT infer an LTE RIL error from missing PS registration, nor infer a
functional dual-LTE stack from selected subscription IDs.
"""
import argparse
import json
from pathlib import Path

def slim(snap):
    slot_map = {int(x["phone_id"]): x for x in snap.get("wwan_registration", [])}
    out = {}
    for i in (0, 1):
        entry = slot_map.get(i, {})
        ps = entry.get("ps_wwan", {})
        cs = entry.get("cs_wwan", {})
        out[str(i)] = {
            "ps_reg": ps.get("registration", "UNKNOWN"),
            "ps_rat": ps.get("rat", "UNKNOWN"),
            "cs_reg": cs.get("registration", "UNKNOWN"),
            "cs_rat": cs.get("rat", "UNKNOWN"),
            "ps_lte_registered": bool(entry.get("ps_lte_registered", False)),
        }
    return out

def analyze(before, after):
    before_sub = before.get("subscription_mapping", {}).get("default_data_sub_id")
    after_sub = after.get("subscription_mapping", {}).get("default_data_sub_id")
    active = after.get("subscription_mapping", {}).get("active_data_sub_id")
    slots_before = slim(before)
    slots_after = slim(after)
    if before_sub != 1 or after_sub != 2 or active != 2:
        label = "DDS_NOT_CONFIRMED"
        next_check = "Confirm default AND active data subscription changed from 1 to 2."
    elif slots_after["1"]["ps_lte_registered"]:
        label = ("DUAL_WWAN_LTE_PS" if slots_after["0"]["ps_lte_registered"]
                 else "MOBIFONE_LTE_HANDOFF")
        next_check = "Test real mobile Internet, call, and radio stability. No firmware success implied."
    elif slots_after["1"]["ps_reg"] in ("HOME", "ROAMING"):
        label = "MOBIFONE_REGISTERED_NON_LTE_PS"
        next_check = "SIM2 mobile-data service is registered but not LTE. Inspect modem RAF ownership."
    elif slots_after["1"]["ps_reg"] == "NOT_REG_OR_SEARCHING":
        label = "SIM2_PS_NOT_REGISTERED"
        next_check = "Inspect PhoneSwitcher, ProxyController RAF and RIL logs immediately after switching."
    else:
        label = "SIM2_PS_REGISTRATION_UNKNOWN"
        next_check = "Capture a fresh sanitized --snapshot sim2 before diagnosing the modem."
    return {
        "status": label,
        "dds_before": before_sub,
        "dds_after": after_sub,
        "active_data_sub_id_after": active,
        "before_wwan": slots_before,
        "after_wwan": slots_after,
        "dual_lte_proven_by_ps_registration": (slots_after["0"]["ps_lte_registered"]
                                                 and slots_after["1"]["ps_lte_registered"]),
        "possible_causes_not_yet_distinguished": [
            "RAF0 or unsupported Samsung RIL RadioCapability transaction",
            "data network not attached / carrier registration issue",
            "Exynos8895 dual-SIM hardware or firmware limitation"
        ] if label in ("SIM2_PS_NOT_REGISTERED", "SIM2_PS_REGISTRATION_UNKNOWN") else [],
        "next_check": next_check,
        "modem_or_efs_changed": False
    }

def fixture(default, active, reg0, rat0, reg1, rat1):
    def entry(i, reg, rat):
        return {"phone_id": i, "ps_wwan": {"registration": reg, "rat": rat},
                "cs_wwan": {"registration": "HOME",
                            "rat": rat if reg in ("HOME", "ROAMING") else "UMTS"},
                "ps_lte_registered": reg in ("HOME", "ROAMING") and rat == "LTE"}
    return {
      "subscription_mapping":{"default_data_sub_id": default,
                              "active_data_sub_id": active},
      "wwan_registration":[entry(0,reg0,rat0),entry(1,reg1,rat1)]
    }

def selftest():
    a = fixture(1,1,"HOME","LTE","NOT_REG_OR_SEARCHING","UMTS")
    b = fixture(2,2,"NOT_REG_OR_SEARCHING","UMTS","NOT_REG_OR_SEARCHING","UMTS")
    assert analyze(a,b)["status"] == "SIM2_PS_NOT_REGISTERED"
    assert not analyze(a,b)["dual_lte_proven_by_ps_registration"]
    c = fixture(2,2,"NOT_REG_OR_SEARCHING","UMTS","HOME","UMTS")
    assert analyze(a,c)["status"] == "MOBIFONE_REGISTERED_NON_LTE_PS"
    d = fixture(2,2,"NOT_REG_OR_SEARCHING","UMTS","HOME","LTE")
    assert analyze(a,d)["status"] == "MOBIFONE_LTE_HANDOFF"
    e = fixture(2,2,"HOME","LTE","HOME","LTE")
    assert analyze(a,e)["status"] == "DUAL_WWAN_LTE_PS"
    f = fixture(1,1,"HOME","LTE","NOT_REG_OR_SEARCHING","UMTS")
    assert analyze(a,f)["status"] == "DDS_NOT_CONFIRMED"
    print("PASS: S8+ DDS=2 registered/nonregistered/LTE dual-slot diagnostic fixtures")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path)
    ap.add_argument("--after", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.before or not args.after:
        ap.error("--before and --after are required")
    print(json.dumps(analyze(json.loads(args.before.read_text()),
                             json.loads(args.after.read_text())),
                     ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
