#!/usr/bin/env python3
"""ALICE S8+ Android16 read-only dual-SIM LTE audit folder analyzer."""
from __future__ import annotations
import argparse, re
from pathlib import Path

FIELDS = {
 "voice registration":r"\bmVoiceRegState\s*=\s*([A-Z_0-9]+(?:\([A-Z_]+\))?)",
 "data registration":r"\bmDataRegState\s*=\s*([A-Z_0-9]+(?:\([A-Z_]+\))?)",
 "data RAT":r"\bmRilDataRadioTechnology\s*=\s*([A-Za-z_0-9]+)",
 "voice RAT":r"\bmRilVoiceRadioTechnology\s*=\s*([A-Za-z_0-9]+)",
 "data network":r"\bm(?:mDataNetworkType|dataNetworkType)\s*=\s*([A-Za-z_0-9]+)",
 "phone id":r"\bm(?:PhoneId|phoneId)\s*[:=]\s*(\d+)",
 "radio access family":r"\b(?:mRadioAccessFamily|mRaf|raf)\s*[:=]\s*(\d+)",
}
ERRORS = {
 "Invalid RadioCapability":r"(?:responseRadioCapability.{0,100}Invalid response|Invalid response.{0,100}(?:RADIO_CAPABILITY|RadioCapability))",
 "RAF fallback zero":r"Faking\s+RIL_REQUEST_GET_RADIO_CAPABILITY\s+response\s+using\s+0",
 "CP rejects second LTE stack":r"LTE\s+is\s+configured\s+on\s+other\s+stack",
 "RADIO_NOT_AVAILABLE":r"RADIO_NOT_AVAILABLE",
 "OUT_OF_SERVICE":r"OUT_OF_SERVICE",
 "GET_BARRING_INFO unsupported":r"GET_BARRING_INFO.{0,120}REQUEST_NOT_SUPPORTED",
}
SAFE_PROPS = {"gsm.network.type","gsm.network.type.2","gsm.sim.state","gsm.sim.state.2",
              "ro.telephony.default_network","ro.vendor.sec.radio.def_network",
              "persist.radio.multisim.config","ro.vendor.multisim.simslotcount"}

def read(folder,name):
 p=folder/name
 return p.read_text(encoding="utf-8",errors="replace") if p.is_file() else ""

def per_phone_state(raw):
    """Extract only anonymized Phone Id sections from Android16 TelephonyRegistry."""
    raw = raw.split("last known state:", 1)[-1]
    marks = list(re.finditer(r"(?m)^\\s*Phone Id\\s*=\\s*([0-9]+)\\s*$", raw))
    states = []
    for i, mark in enumerate(marks):
        phone = int(mark.group(1))
        if phone not in (0, 1):
            continue
        end = marks[i+1].start() if i+1 < len(marks) else len(raw)
        section = raw[mark.end():end]
        service = next((x for x in section.splitlines() if re.match(r"\\s*mServiceState=", x)), "")
        vr = re.search(r"\\bmVoiceRegState\\s*=\\s*\\d+\\(([A-Z_]+)\\)", service)
        dr = re.search(r"\\bmDataRegState\\s*=\\s*\\d+\\(([A-Z_]+)\\)", service)
        rat = re.search(r"\\bmRilDataRadioTechnology\\s*=\\s*(?:\\d+\\(([A-Z0-9_+]+)\\)|([A-Z0-9_+]+))", service, re.I)
        states.append((phone, vr.group(1) if vr else "?",
                       dr.group(1) if dr else "?",
                       (rat.group(1) or rat.group(2)) if rat else "?"))
    return states


def analyze(folder):
 if not folder.is_dir():raise SystemExit(f"Missing capture folder: {folder}")
 print("=== ALICE S8+ Android16 SIM LTE read-only summary ===")
 print("Captured folder:",folder.name)
 allowed=[]
 for idx in (0,1):
  s=read(folder,f"slot{idx}_allowed.txt").strip()
  if not re.fullmatch(r"[A-Z0-9+_|\s]+",s):s="unavailable"
  allowed.append(s)
  print(f"SIM{idx+1} user allowed:",s)
 print("Safe network properties:")
 for line in (read(folder,"radio_props.txt")+"\n"+read(folder,"android_versions.txt")).splitlines():
  if "=" not in line:continue
  k,v=line.split("=",1)
  if k.strip() in SAFE_PROPS and re.fullmatch(r"[A-Za-z0-9._,\-]*",v.strip()):
   print(f"  {k.strip()}: {v.strip()}")
 print("PER-PHONE REGISTRATION (from Android 16 TelephonyRegistry Phone Id sections):")
 per_phone=per_phone_state(read(folder,"service_telephony_registry.txt"))
 if not per_phone:
  print("  Phone Id records unavailable; do not assign global service states to SIMs.")
 for phone, voice, data, rat in per_phone:
  print(f"  SIM{phone+1}/PhoneId{phone}: voice={voice} data={data} RAT={rat}")
 print("Radio registration fields (not attributed to individual SIM unless phoneId is present):")
 for n in ("service_phone.txt","service_telephony_registry.txt"):
  body=read(folder,n)
  if not body:continue
  print(f" {n}:")
  present=0
  for field,pat in FIELDS.items():
   vals=list(dict.fromkeys(re.findall(pat,body,re.I)))[:12]
   if vals:
    present+=1
    print(f"   {field}: {', '.join(vals)}")
  if not present:print("   no recognized fields")
 logs=read(folder,"radio_filtered.log")+"\n"+read(folder,"framework_radio.log")
 print("RIL/CP log signatures (all phones combined):")
 for name,pat in ERRORS.items():
  matches=len(re.findall(pat,logs,re.I))
  if matches:print(f"  {name}: {matches}")
 print("Interpretation:")
 if all("LTE" in a for a in allowed):
  print("  LTE is already in both USER masks; do NOT blindly force masks again.")
 if re.search(ERRORS["CP rejects second LTE stack"],logs,re.I):
  print("  Modem rejected simultaneous LTE: investigate single LTE hand-off.")
 if re.search(ERRORS["RAF fallback zero"],logs,re.I):
  print("  RadioCapability RAF=0 fallback found: investigate framework/RIL negotiation.")
 print("  Allowed LTE does NOT prove current LTE network registration.")
 print("  Redact IMEI/IMSI/ICCID, subscriber and cell data from raw logs before sharing.")

if __name__=="__main__":
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("folder",nargs="?")
 args=parser.parse_args()
 if args.folder:folder=Path(args.folder).expanduser()
 else:
  folders=[p for p in sorted((Path.home()/"Downloads").glob("ALICE_A16_SIM_LTE_*"),reverse=True) if p.is_dir()]
  if not folders:parser.error("No capture in ~/Downloads")
  folder=folders[0]
 analyze(folder)
