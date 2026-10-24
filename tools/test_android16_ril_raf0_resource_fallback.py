#!/usr/bin/env python3
"""Offline test of the SOURCE-ONLY, default-OFF Samsung S8+ RIL.java RAF0 trial.

The test establishes unified-diff applicability to an AOSP-shaped RIL snippet
and ensures there is no fake Qualcomm/CP/EFS or implicit runtime enablement.
It does NOT establish ROM integration, RIL fix success, or hardware dual LTE.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/android16/0002-RIL-S8Plus-both-phones-RAF0-resource-fallback-OPTIN.patch"
RIL_PATH = Path("src/java/com/android/internal/telephony/RIL.java")
ORIGINAL = (
    "        if (!TextUtils.isEmpty(rafString)) {\n"
    "            raf = RadioAccessFamily.rafTypeFromString(rafString);\n"
    "        }\n"
    "        RadioCapability rc = new RadioCapability(mPhoneId.intValue(), 0, 0, raf,\n"
)

def main():
    s = PATCH.read_text()
    assert all(part in s for part in (
        "diff --git a/src/java/com/android/internal/telephony/RIL.java",
        "raf == RadioAccessFamily.RAF_UNKNOWN",
        '"dream2lte".equals(',
        '"persist.vendor.alice.s8p_raf0_resource_fallback", false',
        "android.content.res.Resources.getSystem()",
        "config_radio_access_family",
        "RadioAccessFamily.rafTypeFromString(systemRafString)",
        "raf = parsedSystemRaf;",
        "ALICE_RAF0_RESOURCE_FALLBACK",
    )), "RIL trial missing critical zero/opt-in/device gates"
    assert "getPhoneId() == 1" not in s, "both PHONE0 and PHONE1 need recovery"
    assert not any(token in s for token in (
        "setprop", "NON-HLOS", "modem.bin", "persist.radio.multisim.config",
        "/efs", "ro.telephony.default_network=9,9", "getRafFromNetworkType"
    )), "modem/RAT forcing must not be in source fallback"
    assert shutil.which("patch"), "GNU patch required for CI selftest"
    with tempfile.TemporaryDirectory() as temp:
        dst = Path(temp) / RIL_PATH
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(ORIGINAL)
        result = subprocess.run(
            ["patch", "--batch", "-p1", "-i", str(PATCH)],
            cwd=temp, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        modified = dst.read_text()
        assert modified.count("raf = parsedSystemRaf;") == 1
        assert modified.index("raf = parsedSystemRaf;") < modified.index("RadioCapability rc =")
        assert re.search(r's8p_raf0_resource_fallback", false\)', modified)
    print("PASS: both-phone, default-OFF S8+ RIL RAF0 system-resource fallback diff applies to AOSP-shaped snippet")
    print("NOTE: source patch NOT applied to running Android16 ROM; no LTE result is implied.")

if __name__ == "__main__":
    main()
