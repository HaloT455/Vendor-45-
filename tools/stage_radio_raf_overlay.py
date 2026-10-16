#!/usr/bin/env python3
"""Build signed, isolated radio capability fallback RRO for Test7 (research only).

This does not fake modem capabilities. It supplies AOSP's documented
config_radio_access_family resource for legacy RILs whose
GET_RADIO_CAPABILITY is unsupported. Android 16 framework idmap/overlayable
policy MUST be verified with the user's exact system image at runtime.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

RAF = "GSM|WCDMA|LTE"
NAME = "com.alice.radio.raf.overlay"


def run(*cmd):
    subprocess.run([str(x) for x in cmd], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("out/ALICE-RadioRAF.apk"))
    args = ap.parse_args()
    sdk = args.sdk
    aapt2 = sdk / "build-tools/36.0.0/aapt2"
    apksigner = sdk / "build-tools/36.0.0/apksigner"
    framework = sdk / "platforms/android-36/android.jar"
    assert all(x.is_file() for x in (aapt2, apksigner, framework)), (
        "Requires Android SDK 36, build-tools 36.0.0 and platform android-36")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="alice-raf-rro-") as t:
        root = Path(t)
        (root / "res/values").mkdir(parents=True)
        (root / "res/xml").mkdir(parents=True)
        manifest = root / "AndroidManifest.xml"
        manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n'
            f'  package="{NAME}" android:versionCode="1" android:versionName="1">\n'
            '  <application android:hasCode="false"/>\n'
            '  <overlay android:targetPackage="android" android:targetName="FrameworkResources"\n'
            '           android:resourcesMap="@xml/overlays" android:isStatic="true"\n'
            '           android:priority="9"/>\n'
            '</manifest>\n'
        )
        (root / "res/values/strings.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources><string name="alice_radio_access_family" translatable="false">'
            + RAF + '</string></resources>\n'
        )
        (root / "res/xml/overlays.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<overlay><item target="string/config_radio_access_family"'
            ' value="@string/alice_radio_access_family"/></overlay>\n'
        )
        ET.parse(manifest)
        ET.parse(root / "res/xml/overlays.xml")
        run(aapt2, "compile", "--dir", root / "res", "-o", root / "compiled.zip")
        run(aapt2, "link", "-I", framework, "--manifest", manifest,
            "--auto-add-overlay", "--no-resource-deduping", "--no-resource-removal",
            "-o", root / "unsigned.apk", root / "compiled.zip")
        ks = root / "debug-only.jks"
        run("keytool", "-genkeypair", "-alias", "androiddebugkey",
            "-storetype", "JKS", "-keystore", ks,
            "-storepass", "android", "-keypass", "android",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "3",
            "-dname", "CN=ALICE Research Only, OU=Unverified, O=Prototype, C=VN",
            "-noprompt")
        run(apksigner, "sign", "--ks", ks, "--ks-key-alias", "androiddebugkey",
            "--ks-pass", "pass:android", "--key-pass", "pass:android",
            "--out", args.output, root / "unsigned.apk")
        run(apksigner, "verify", args.output)
        resources = subprocess.check_output([str(aapt2), "dump", "resources",
                                             str(args.output)], text=True)
        manifest_text = subprocess.check_output([str(aapt2), "dump", "xmltree",
                                                  str(args.output), "AndroidManifest.xml"],
                                                 text=True)
        assert "alice_radio_access_family" in resources, "Compiled RAF resource missing"
        assert "overlays" in resources, "Compiled resourcesMap missing"
        assert "com.alice.radio.raf.overlay" in manifest_text, "Package ID missing"
        assert args.output.stat().st_size > 2000
    print(json.dumps({
        "overlay": str(args.output), "bytes": args.output.stat().st_size,
        "radio_access_family": RAF, "framework_resource": "config_radio_access_family",
        "signed": True, "static_rro": True, "device_idmap_verified": False,
        "modem_changed": False, "flash_ready": False
    }))


if __name__ == "__main__":
    main()
