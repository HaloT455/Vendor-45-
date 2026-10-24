#!/usr/bin/env python3
"""Static/offline unit test of opt-in Phone.java trial diff (no device writes).

A passing result establishes that the unified diff applies to the AOSP
updateAllowedNetworkTypes() anchor and has an explicit default-OFF guard.
It does NOT test Android16 Java compilation, Samsung RIL, or LTE registration.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import tempfile

PATCH = Path(__file__).resolve().parents[1] / "patches/android16/0001-Phone-optional-S8Plus-phone1-RAF0-framework-fallback.patch"
SOURCE = Path("src/java/com/android/internal/telephony/Phone.java")
UNMODIFIED = """\
    protected void updateAllowedNetworkTypes(Message response) {
        int modemRaf = getRadioAccessFamily();
        if (modemRaf == RadioAccessFamily.RAF_UNKNOWN) {
"""


def main() -> None:
    patch = PATCH.read_text(encoding="utf-8")
    mandatory = (
        "diff --git a/src/java/com/android/internal/telephony/Phone.java",
        "getPhoneId() == 1",
        "persist.vendor.alice.s8p_raf0_fallback",
        "getBoolean(",
        "config_radio_access_family",
        "rafTypeFromString(declaredRaf)",
        "parsedRaf != RadioAccessFamily.RAF_UNKNOWN",
        "modemRaf = parsedRaf;",
        "ALICE_RAF0_TRIAL_PHONE1",
    )
    assert all(token in patch for token in mandatory), "patch lost guard or capability validation"
    assert not any(token in patch for token in (
        "setprop", "ro.telephony.default_network", "persist.radio.multisim.config",
        "ril-daemon", "modem.bin", "NON-HLOS.bin", "/efs", "/dev/block"
    )), "unsafe content in AOSP trial patch"
    if not shutil.which("patch"):
        raise SystemExit("Missing GNU patch; CI must install/use it")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        file = root / SOURCE
        file.parent.mkdir(parents=True)
        file.write_text(UNMODIFIED, encoding="utf-8")
        diff = subprocess.run(
            ["patch", "-p1", "--batch", "--forward", "--input", str(PATCH)],
            cwd=root, text=True, capture_output=True
        )
        assert diff.returncode == 0, "unified diff failed: " + diff.stdout + diff.stderr
        updated = file.read_text(encoding="utf-8")
        assert updated.startswith("    protected void updateAllowedNetworkTypes")
        assert "modemRaf = parsedRaf;" in updated
        assert "if (modemRaf == RadioAccessFamily.RAF_UNKNOWN)" in updated
        assert "false))" in updated, "fallback enabled by default"
        assert updated.count("setAllowedNetworkTypes") == 0, "unexpected modem-write commands"
    print("PASS: disabled-by-default S8+ Phone1 RAF0 source patch applies; not yet ROM-built/tested")


if __name__ == "__main__":
    main()
