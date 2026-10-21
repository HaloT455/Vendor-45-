#!/usr/bin/env python3
"""Read-only audit of the actual extracted ALICE SYSTEM V2 and Samsung Face/Iris UI.

This is SOURCE/COMPATIBILITY TRIAGE, not an unlock bypass, install, or flash.
It does not extract APKs, modify the ROM, or read private biometric templates.
Results describe available files and selected DEX marker presence only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import zipfile

DEFAULT = Path("/mnt/alice-ssd/ALICE_SYSTEM/GITHUB_SYSTEM_V2_IMPORT/SystemDreamlte/system")
LOOKUP = {
    "SecSettings": [
        "priv-app/SecSettings/SecSettings.apk",
        "priv-app/Settings/Settings.apk",
        "app/Settings/Settings.apk",
    ],
    "SystemUI": [
        "system_ext/priv-app/SystemUI/SystemUI.apk",
        "priv-app/SystemUI/SystemUI.apk",
    ],
    "framework": [
        "framework/framework.jar",
        "framework/services.jar",
        "framework/semframework.jar",
        "framework/semservices.jar",
    ],
}
TOKENS = {
    "samsung_iris_manager": b"SemIrisManager",
    "iris_service": b"IrisService",
    "iris_enroll": b"IrisEnroll",
    "face_enroll": b"FaceEnroll",
    "face_manager": b"FaceManager",
    "samsung_face_manager": b"SemFace",
}
PRIVATE = ("efs", "data", "userdata", "persist")


def find_system_root(source: Path) -> Path:
    source = source.expanduser().resolve()
    candidates = [source, source / "system", source / "system" / "system"]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "priv-app").is_dir() and (
            (candidate / "framework").is_dir() or
            (candidate / "etc" / "permissions").is_dir()
        ):
            return candidate
    raise ValueError(f"SYSTEM V2 extraction not detected at {source}; do not use V1")


def apk_tokens(path: Path) -> dict:
    hits = {key: False for key in TOKENS}
    dex_files = 0
    if not zipfile.is_zipfile(path):
        return {"readable_apk_or_jar": False, "dex_files": dex_files, "markers": hits}
    try:
        with zipfile.ZipFile(path) as zf:
            for entry in zf.infolist():
                if not re.fullmatch(r"classes\d*\.dex", Path(entry.filename).name):
                    continue
                if entry.file_size > 70 * 1024 * 1024:
                    continue
                dex_files += 1
                with zf.open(entry) as d:
                    # bounded 70MiB per DEX: no raw data is printed or retained
                    payload=d.read(70*1024*1024 + 1)
                for key,token in TOKENS.items():
                    hits[key] |= token in payload
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return {"readable_apk_or_jar": False, "dex_files": dex_files, "markers": hits}
    return {"readable_apk_or_jar": True, "dex_files": dex_files, "markers": hits}


def audit(root: Path) -> dict:
    system=find_system_root(root)
    for private in PRIVATE:
        target=system / private
        if target.exists() and target.is_dir() and any(target.iterdir()):
            raise ValueError("SYSTEM contains unexpected private mountpoint data: /"+private)
    selected={}
    for group,paths in LOOKUP.items():
        for rel in paths:
            file=system / rel
            if file.is_file():
                selected[rel]=apk_tokens(file)

    # filename-based inventory only; not proof of functional implementation
    markers=[]
    for p in system.rglob("*"):
        if any(v in p.name.lower() for v in ("iris", "face", "biometric")):
            if p.is_file() or p.is_dir():
                markers.append(p.relative_to(system).as_posix())
    markers=sorted(markers)
    advertised={"face": [], "iris": []}
    perm=system/"etc"/"permissions"
    if perm.is_dir():
        for f in perm.glob("*.xml"):
            try:
                if f.stat().st_size>1048576:continue
                text=f.read_text(errors="replace")
            except OSError:continue
            for kind in advertised:
                if f"android.hardware.biometrics.{kind}" in text:
                    advertised[kind].append(f.name)
    report={
        "source_kind":"extracted_SYSTEM_V2_on_Zorin",
        "system_v2_root":str(system),
        "target_apps_examined":selected,
        "biometrics_relevant_file_count":len(markers),
        "biometrics_relevant_paths":markers[:60],
        "permissions_xml_candidates":advertised,
        "iris_menu_runtime_available":None,
        "face_enrollment_runtime_works":None,
        "interpretation":[
            "DEX string markers are hints, not evidence a runnable settings UI exists.",
            "No iris feature XML does not prove iris hardware absent.",
            "Face and iris enrollment need a real secure HAL and matching system framework.",
            "Nothing from this script authenticates users or modifies SYSTEM/vendor."
        ],
    }
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-root",type=Path,default=DEFAULT)
    ap.add_argument("--output",type=Path,help="Optional report JSON location")
    args=ap.parse_args()
    try: result=audit(args.system_root)
    except ValueError as exc:ap.exit(2,f"SYSTEM_V2_AUDIT_ERROR: {exc}\n")
    blob=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.expanduser().write_text(blob)
    print(blob)
if __name__=="__main__":main()
