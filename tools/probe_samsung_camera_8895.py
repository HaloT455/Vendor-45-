#!/usr/bin/env python3
"""Read-only S8+ Exynos8895 camera ABI comparison to S9+ UN1CA.

Do not apply Exynos9810 byte patches to Exynos8895 camera libraries.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/"vendor"
S9_ENTRY="_ZN7android12ExynosCamera21processCaptureRequestEP23camera3_capture_request"
S9_LLS={
"star2lte":"fcf757f908b307bb204604f58475fef7bbfa",
"starlte":"fcf75afc08b307bb204604f58475fef715fb",
"crownlte":"fcf7d1f808b307bb204604f58475fef769fa"}
PARTS=["hw/camera.universal8895.so","libexynoscamera3.so","libexynoscamera.so","libshim_camera.so"]

def readelf(path,option):
    return subprocess.check_output(["readelf",option,"--wide",str(path)],
                                   text=True,stderr=subprocess.PIPE,timeout=35)

def inspect_elf(path):
    data=path.read_bytes()
    if data[:4]!=b"\x7fELF": raise ValueError(f"Not ELF: {path}")
    syms=readelf(path,"-Ws")
    dynamic=readelf(path,"-d")
    return {
      "sha256":hashlib.sha256(data).hexdigest(),
      "class":"ELF64" if data[4]==2 else "ELF32",
      "s9_exact_capture_symbol_present":S9_ENTRY.encode() in data,
      "s9_exact_capture_symbol_exported": any(
          S9_ENTRY in l and " UND " not in l for l in syms.splitlines()),
      "s9_lls_opcode_matches":{k:data.count(bytes.fromhex(v)) for k,v in S9_LLS.items()},
      "capture_symbols":sorted(set(l.split()[-1] for l in syms.splitlines()
          if "processCaptureRequest" in l or "process_capture_request" in l))[:30],
      "needed":sorted(set(re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", dynamic)))}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",default="out/s8-vs-s9-camera-abi.json")
    args=ap.parse_args()
    result={
      "device":"Samsung Galaxy S8+ / Exynos8895",
      "s9_reference":"Eend15/Unofficial-Un1ca-9810@2b25ae6fc3098650be249bd1898e21e563cd5df1",
      "s9_camera_app_version":"16.0.00.74",
      "s9_arm_patch_applied":False,
      "s9_fence_adapter_applied":False,
      "samsung_camera_app_patched":False,
      "physical_device_tested":False,
      "flash_ready":False,
      "elf":{}, "camera_feature":{}, "errors":[]}
    for arch in ("lib","lib64"):
        for part in PARTS:
            name=f"{arch}/{part}"
            path=VENDOR/name
            if not path.is_file():
                result["errors"].append("Missing camera part "+name)
                continue
            try: result["elf"][name]=inspect_elf(path)
            except (OSError,ValueError,subprocess.CalledProcessError) as err:
                result["errors"].append(f"Could not inspect {name}: {err}")
    xml=VENDOR/"etc/alice-test7/camera-feature.xml"
    if not xml.is_file(): result["errors"].append("Camera feature XML missing")
    else:
        matrix={}
        for item in ET.parse(xml).getroot().iter("local"):
            k=item.attrib.get("name","")
            if k.startswith("SHOOTING_MODE_") or k in (
               "BACK_CAMERA_PICTURE_DEFAULT_RESOLUTION",
               "FRONT_CAMERA_PICTURE_DEFAULT_RESOLUTION"):
                matrix[k]=dict(item.attrib)
        result["camera_feature"]["shooting_modes"]={k:v.get("enable")
                for k,v in matrix.items() if k.startswith("SHOOTING_MODE_")}
        result["camera_feature"]["back_default"]=matrix.get("BACK_CAMERA_PICTURE_DEFAULT_RESOLUTION")
        result["camera_feature"]["front_default"]=matrix.get("FRONT_CAMERA_PICTURE_DEFAULT_RESOLUTION")
    rc=VENDOR/"etc/init/alice-camera-test7.rc"
    result["camera_feature"]["bind_mount_declared"] = (rc.is_file() and
        "mount none /vendor/etc/alice-test7/camera-feature.xml /system/cameradata/camera-feature.xml bind" in rc.read_text())
    result["s9_capture_entry_exists_both_8895"] = all(result["elf"].get(
        f"{abi}/libexynoscamera3.so",{}).get("s9_exact_capture_symbol_exported",False)
        for abi in ("lib","lib64"))
    result["s9_arm_lls_patch_is_safe_to_transplant"]=False
    result["next_step"]="Get actual One UI 8 S8+ SamsungCamera.apk and framework files from the booted ROM/system image; verify photo smali and crash log. Vendor.img alone cannot restore a deleted system privileged app."
    dest=Path(args.output); dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"elf_count":len(result["elf"]),
                      "s9_capture_entry_exists_both_8895":result["s9_capture_entry_exists_both_8895"],
                      "errors":result["errors"],"camera_fixed":False,"flash_ready":False}))
    if result["errors"]: raise SystemExit(2)

if __name__=="__main__":main()
