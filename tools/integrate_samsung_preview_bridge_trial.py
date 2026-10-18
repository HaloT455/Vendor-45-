#!/usr/bin/env python3
"""Integrate experimental ALICE preview tag bridge on ephemeral vendor checkout.

Must run AFTER pinned UN1GAGA stage; keeps legacy native camera HAL and original
UN1GAGA wrapper, including 32/64-bit variants, for no-loss delegation.
Do NOT claim a camera or boot test from ELF/Erofs CI.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"metadata/vendor-image-manifest.json"
FS=ROOT/"metadata/vendor_fs_config"
FC=ROOT/"metadata/vendor_file_contexts"

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage",type=Path,required=True)
    ap.add_argument("--report",type=Path,default=Path("out/samsung-preview-bridge-trial.json"))
    args=ap.parse_args()
    j=json.loads(M.read_text())
    manifest={e["path"]:e for e in j["entries"]}
    assert len(manifest)==1431,"Pinned UN1GAGA camera integration must run first"
    changes=[]
    staging=[]
    for abi,expected_class in (("lib",1),("lib64",2)):
        src=f"{abi}/hw/camera.universal8895.so"
        dst=f"{abi}/hw/camera.alice-hlong.universal8895.so"
        backup=f"{abi}/hw/camera.vendor.universal8895.so"
        assert src in manifest and backup in manifest and dst not in manifest
        item=manifest[src]
        assert item["type"]=="file" and item["nlink"]==1
        tag=base64.b64decode(item["xattrs"]["security.selinux"])
        assert tag==b"u:object_r:vendor_file:s0"
        previous=(ROOT/"vendor"/src).read_bytes()
        legacy=(ROOT/"vendor"/backup).read_bytes()
        compiled=(args.stage/"vendor"/src).read_bytes()
        for what,payload in (("UN1GAGA",previous),("Exynos8895 stock",legacy),
                             ("ALICE preview bridge",compiled)):
            assert payload[:4]==b"\x7fELF" and payload[4]==expected_class,(what,abi)
        assert b"availablePreviewStreamConfigurations" in compiled
        assert b"availablePictureStreamConfigurations" in compiled
        assert b"availableVideoConfigurations" in compiled
        assert b"camera.alice-hlong.universal8895.so" in compiled
        staging.append((abi,src,dst,item,previous,compiled))
    next_nid=max(e["nid"] for e in manifest.values())+512
    for abi,src,dst,item,previous,compiled in staging:
        output=ROOT/"vendor"/dst
        assert not output.exists()
        output.write_bytes(previous)
        (ROOT/"vendor"/src).write_bytes(compiled)
        e=copy.deepcopy(item)
        e.update(path=dst,nid=next_nid,size=len(previous),
                 sha256=hashlib.sha256(previous).hexdigest())
        j["entries"].append(e)
        next_nid+=512
        with FS.open("a") as f:
            f.write(f"vendor/{dst} 0 0 0644\n")
        with FC.open("a") as f:
            f.write(f"/vendor/{dst.replace('.', chr(92)+'.')} u:object_r:vendor_file:s0\n")
        changes.append({"abi":abi,"proxy":src,"upstream_hlong_backup":dst,
                        "upstream_sha256":hashlib.sha256(previous).hexdigest(),
                        "bridge_sha256":hashlib.sha256(compiled).hexdigest(),
                        "legacy_hal":f"{abi}/hw/camera.vendor.universal8895.so"})
    j["entries"].sort(key=lambda x:x["path"])
    M.write_text(json.dumps(j,indent=2,ensure_ascii=False)+"\n")
    assert len(j["entries"])==1433
    report={"changes":changes,"image_entries_after_bridge":1433,
            "samsung_preview_tag":"samsung.android.scaler.availablePreviewStreamConfigurations",
            "samsung_picture_tag":"samsung.android.scaler.availablePictureStreamConfigurations",
            "samsung_video_tag":"samsung.android.scaler.availableVideoConfigurations",
            "video_tag_layout_confirmed_on_device":False,
            "expected_vendor_tag_type":"int32 stream configuration tuples; format 34 PRIVATE for preview and format 33 BLOB for JPEG",
            "stock_samsung_vendor_tags_preserved_by_delegation":True,
            "actual_provider_registration_verified":False,
            "actual_camera2_metadata_verified":False,
            "samsung_apk_16_5_preview_verified":False,
            "samsung_apk_16_5_picture_verified":False,
            "boot_verified":False,"flash_ready":False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
