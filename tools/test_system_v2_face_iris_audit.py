#!/usr/bin/env python3
"""Local synthetic fixture tests for extracted SYSTEM V2 Face/Iris audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alice_system_v2_face_iris_audit import audit, find_system_root, apk_tokens

with TemporaryDirectory() as tmp:
    p=Path(tmp)
    root=p/"system"/"system"
    (root/"framework").mkdir(parents=True)
    (root/"priv-app"/"SecSettings").mkdir(parents=True)
    (root/"system_ext"/"priv-app"/"SystemUI").mkdir(parents=True)
    (root/"etc"/"permissions").mkdir(parents=True)
    with ZipFile(root/"priv-app"/"SecSettings"/"SecSettings.apk","w") as zf:
        zf.writestr("classes.dex",b"fake classes for TEST SemIrisManager FaceEnroll")
    with ZipFile(root/"system_ext"/"priv-app"/"SystemUI"/"SystemUI.apk","w") as zf:
        zf.writestr("classes.dex",b"just some fake test data")
    (root/"etc"/"permissions"/"face-test.xml").write_text(
        '<permissions><feature name="android.hardware.biometrics.face"/></permissions>')
    (root/"etc"/"permissions"/"empty.xml").write_text("<permissions/>")
    (root/"etc"/"security-iris-service").mkdir(parents=True)
    assert find_system_root(p) == root
    report=audit(p)
    assert report["target_apps_examined"]["priv-app/SecSettings/SecSettings.apk"]["markers"]["samsung_iris_manager"]
    assert report["target_apps_examined"]["priv-app/SecSettings/SecSettings.apk"]["markers"]["face_enroll"]
    assert report["permissions_xml_candidates"]["face"]==["face-test.xml"]
    assert report["permissions_xml_candidates"]["iris"]==[]
    assert report["iris_menu_runtime_available"] is None
    assert report["face_enrollment_runtime_works"] is None
    (root/"efs").mkdir()
    assert audit(p)["system_v2_root"]==str(root)
    (root/"efs"/"personal.bin").write_bytes(b"FAKE TEST ONLY")
    try:
        audit(p)
    except ValueError as e:assert "private" in str(e)
    else:raise AssertionError("private data was not rejected")
    print("PASS: SYSTEM V2 tree discovery, real APK ZIP DEX marker scan, Face feature XML and EFS guard")
