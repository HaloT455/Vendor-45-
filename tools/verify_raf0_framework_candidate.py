#!/usr/bin/env python3
"""Check ALICE Android16 HIDL RadioResponse RAF=0 candidate against exact source.

Requires a copy of upstream RadioResponse.java and javac on the CI runner.
Only compiles isolated mocks of the patched GET_CAPABILITY method; not a full
Android build and not proof of real LTE attach. No device interactions.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "research/patches/0001-radioresponse-raf0-success-fallback-RESEARCH.patch"
RELATIVE_SRC = "src/java/com/android/internal/telephony/RadioResponse.java"
START = "    public void getRadioCapabilityResponse("
END = "    public void setRadioCapabilityResponse("

def run(*args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd,
        check=True, text=True, capture_output=True).stdout

def extract(text):
    a = text.index(START)
    b = text.index(END, a)
    return text[a:b].rstrip()

def validate(source: Path):
    before = source.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="alice-raf0-verify-") as d:
        root = Path(d)
        dest = root / RELATIVE_SRC
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(before, encoding="utf-8")
        run("git", "apply", "--check", PATCH, cwd=root)
        run("git", "apply", PATCH, cwd=root)
        after = dest.read_text(encoding="utf-8")
        oldmethod, method = extract(before), extract(after)
        assert before.replace(oldmethod, method, 1) == after, "Non-RC code changed"
        assert before.count(oldmethod) == 1
        assert "else if (responseInfo.error == RadioError.NONE" in method
        assert "ret.getRadioAccessFamily()" in method
        assert "mRil.makeStaticRadioCapability()" in method
        assert "fallback.getRadioAccessFamily()" in method
        assert "responseInfo.error = RadioError.NONE;" in method
        # A no-op if the entire static RAF fallback is still UNKNOWN.
        assert "if (fallback.getRadioAccessFamily()" in method
        assert method.count("mRil.processResponseDone(rr, responseInfo, ret)") == 1
        assert method.count("sendMessageResponse(rr.mResult, ret)") == 1
        assert "android.telephony.RadioAccessFamily.RAF_UNKNOWN" in method
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            raise RuntimeError("JDK 17+ required for isolated Java execution tests")

        # Minimal stubs exercise the ACTUAL patched method byte for byte.
        def mk(path, body):
            p=root/"mock"/path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
            return p
        files = [
            mk("android/telephony/RadioAccessFamily.java", """
package android.telephony;
public final class RadioAccessFamily { public static final int RAF_UNKNOWN = 0; }
"""),
            mk("android/hardware/radio/V1_0/RadioError.java", """
package android.hardware.radio.V1_0;
public final class RadioError {
 public static final int NONE=0, REQUEST_NOT_SUPPORTED=6, GENERIC_FAILURE=2;
}
"""),
            mk("android/hardware/radio/V1_0/RadioResponseInfo.java", """
package android.hardware.radio.V1_0;
public final class RadioResponseInfo {
 public int error;
 public RadioResponseInfo(int error) {this.error=error;}
}
"""),
            mk("android/hardware/radio/V1_0/RadioCapability.java", """
package android.hardware.radio.V1_0;
public final class RadioCapability {
 public int raf;
 public RadioCapability(int raf) {this.raf=raf;}
}
"""),
        ]
        harness = """
package com.android.internal.telephony;
import android.hardware.radio.V1_0.RadioResponseInfo;
import android.hardware.radio.V1_0.RadioError;
class RadioCapability {
 private final int raf;
 RadioCapability(int raf) {this.raf=raf;}
 int getRadioAccessFamily() {return raf;}
}
class RILRequest { Object mResult = new Object(); }
class RIL {
 int fallbackRaf, fallbackCalls, sendCalls;
 RadioCapability result;
 int error;
 RIL(int fallbackRaf) {this.fallbackRaf=fallbackRaf;}
 RILRequest processResponse(RadioResponseInfo info) {return new RILRequest();}
 RadioCapability makeStaticRadioCapability() {
   fallbackCalls++; return new RadioCapability(fallbackRaf);
 }
 void processResponseDone(RILRequest rr, RadioResponseInfo info, RadioCapability ret) {
   this.result=ret; this.error=info.error;
 }
}
class RILUtils {
 static RadioCapability convertHalRadioCapability(
   android.hardware.radio.V1_0.RadioCapability rc, RIL ril) {
   return rc==null ? null : new RadioCapability(rc.raf);
 }
}
class RadioResponse {
 RIL mRil;
 RadioResponse(RIL ril) {mRil=ril;}
 static int sent; static int sentRaf;
 static void sendMessageResponse(Object msg, RadioCapability ret) {
   sent++; sentRaf=ret.getRadioAccessFamily();
 }
""" + method + """
}
public class Harness {
 static void check(String title, int error, int raf, int fallback,
                   int result, int fallbackCalls, int sends, int resultingError) {
    RIL ril=new RIL(fallback);
    RadioResponse.sent=0;
    RadioResponse.sentRaf=-1;
    new RadioResponse(ril).getRadioCapabilityResponse(
        new RadioResponseInfo(error), new android.hardware.radio.V1_0.RadioCapability(raf));
    if ((ril.result == null ? -1 : ril.result.getRadioAccessFamily())!=result
        || ril.fallbackCalls!=fallbackCalls
        || RadioResponse.sent!=sends || ril.error!=resultingError
        || (sends>0 && RadioResponse.sentRaf!=result)) {
        throw new AssertionError(title + ": unexpected result/side effects");
    }
    System.out.println("PASS " + title);
 }
 public static void main(String[] args) {
    check("valid LTE modem reply unchanged", 0,4096,123,4096,0,1,0);
    check("success with RAF0 uses real static fallback",0,0,4096,4096,1,1,0);
    check("success with RAF0 and unknown static RAF stays unknown",0,0,0,0,1,1,0);
    check("unsupported preserves upstream fallback",6,0,4096,4096,1,1,0);
    check("generic failure preserves upstream fallback",2,0,4096,4096,1,1,0);
    check("unexpected error not hidden by fallback",17,0,4096,0,0,0,17);
 }
}
"""
        files.append(mk("com/android/internal/telephony/Harness.java", harness))
        classes=root/"classes"
        classes.mkdir()
        run(javac,"-encoding","UTF-8","-d",classes,*files)
        result=run(java,"-cp",classes,"com.android.internal.telephony.Harness")
        print(result,end="")
        print("PASS: patch applies cleanly to fetched framework source")
        print("SCOPE: research-only isolated method test; NO Android system build, flash, or LTE attach verification")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    args=p.parse_args()
    validate(args.source)
