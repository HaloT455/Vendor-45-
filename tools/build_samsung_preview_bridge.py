#!/usr/bin/env python3
"""Cross-compile ALICE Exynos8895 Camera2 vendor-tag bridge in pinned Android NDK.

Never use the host ELF as a target payload. ABI is 32/64 native Android, not S9.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ndk",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=Path("out/stage_preview_bridge"))
    args=ap.parse_args()
    ndk=args.ndk/"toolchains/llvm/prebuilt/linux-x86_64/bin"
    clang=ndk/"clang"
    readelf=ndk/"llvm-readelf"
    assert clang.exists() and readelf.exists(),f"Missing NDK tools at {ndk}"
    src=ROOT/"tools/native_camera/alice_preview_bridge.c"
    output=args.output
    report={"source":str(src.relative_to(ROOT)),"ndk":str(args.ndk),
            "targets":[],"device_tested":False,"flash_ready":False}
    for abi,triple,elf in [
        ("lib","armv7a-linux-androideabi28","ELF32"),
        ("lib64","aarch64-linux-android28","ELF64")
    ]:
        dest=output/"vendor"/abi/"hw"/"camera.universal8895.so"
        dest.parent.mkdir(parents=True,exist_ok=True)
        cmd=[str(clang),f"--target={triple}","-O2","-fPIC","-shared",
             "-Wall","-Wextra","-Werror","-fno-strict-aliasing",
             "-Wl,-z,relro,-z,now","-Wl,-soname,camera.universal8895.so",
             str(src),"-o",str(dest),"-ldl","-llog","-pthread"]
        subprocess.run(cmd,check=True)
        header=subprocess.check_output([str(readelf),"-h",str(dest)],text=True)
        assert ("Class:                             "+elf) in header,header
        symbols=subprocess.check_output([str(readelf),"--dyn-syms","--wide",str(dest)],text=True)
        assert any(line.strip().endswith(" HMI") and " GLOBAL " in line
                   for line in symbols.splitlines()),"Camera module HMI not exported"
        data=dest.read_bytes()
        assert b"samsung.android.scaler" in data
        assert b"availablePreviewStreamConfigurations" in data
        assert b"camera.alice-hlong.universal8895.so" in data
        report["targets"].append({"abi":abi,"target":triple,"sha256":hashlib.sha256(data).hexdigest(),
                                   "bytes":len(data),"path":str(dest),"camera_module_HMI":True})
    output.mkdir(parents=True,exist_ok=True)
    (output/"build-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
