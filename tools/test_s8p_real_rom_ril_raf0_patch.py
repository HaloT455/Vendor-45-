#!/usr/bin/env python3
"""Validates ALICE trial patch against EXACT JADX method body reported by S8+.

This is an OFFLINE source-method regression test, NOT a DEX build or safe
replacement for BOOTCLASSPATH telephony-common.jar. DEX verification and
recovery/rollback remain mandatory before any phone modification.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/android16/0003-S8Plus-OneUI8-RIL-REAL-METHOD-RAF0-FALLBACK-OPTIN.patch"
ROM_METHOD = """\
    RadioCapability makeStaticRadioCapability() {
        RadioCapability radioCapability = new RadioCapability(this.mPhoneId.intValue(), 0, 0, 0, PhoneConfigurationManager.SSSS, 1);
        riljLog("Faking RIL_REQUEST_GET_RADIO_CAPABILITY response using 0");
        return radioCapability;
    }
"""

def main() -> None:
    content = PATCH.read_text()
    for token in (
        "dream2lte",
        "persist.vendor.alice.s8p_raf0_resource_fallback",
        "false))",
        "Resources.getSystem()",
        "config_radio_access_family",
        "rafTypeFromString(rafString)",
        "fallbackRaf = parsedRaf;",
        "new RadioCapability(this.mPhoneId.intValue(),",
        "0, 0, fallbackRaf, PhoneConfigurationManager.SSSS, 1",
    ):
        assert token in content, f"Missing required trial guard: {token}"
    assert all(x not in content for x in (
        "NON-HLOS", "modem.bin", "/efs", "/dev/block",
        "setPreferredNetworkType", "SystemProperties.set(",
    )), "Unexpected modem or system mutation"
    if shutil.which("patch") is None:
        raise SystemExit("GNU patch is required")
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / "com/android/internal/telephony/RIL.java"
        file.parent.mkdir(parents=True)
        file.write_text(ROM_METHOD)
        run = subprocess.run(
            ["patch", "--batch", "--forward", "-p1", "--input", str(PATCH)],
            cwd=directory, text=True, capture_output=True)
        assert run.returncode == 0, run.stdout + run.stderr
        body = file.read_text()
        assert 'new RadioCapability(this.mPhoneId.intValue(),' in body
        assert '0, 0, fallbackRaf, PhoneConfigurationManager.SSSS, 1' in body
        assert "rafTypeFromString(rafString)" in body
        assert "true))" not in body, "Fallback must be opt-in, default OFF"
    print("PASS: user-S8+ exact JADX fallback-method patch + OFF-by-default guards")
    print("SOURCE-ONLY: no JAR/DEX rebuild or on-device patching has been verified")

if __name__ == "__main__":
    main()
