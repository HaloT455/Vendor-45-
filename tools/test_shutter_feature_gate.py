#!/usr/bin/env python3
"""Guard shutter-lag *hypothesis test*: only two Photo feature flags may change.

The user's 4-5 second delay might involve 3A, ZSL, JPEG or app processing.
Disabling scene optimizer and auto Photo Night is an AB test, not a proven fix.
Never change Camera HAL or the user-confirmed Video6 tuples in this branch.
"""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PATH="vendor/etc/alice-test7/camera-feature.xml"
BASE="work/a16-camera-fast-metadata-face-iris-audit"
flags={"SUPPORT_SCENE_OPTIMIZER","SUPPORT_PHOTO_NIGHT"}


def parse(blob:bytes):
    root=ET.fromstring(blob)
    return {(e.tag,e.attrib.get("name"),i):dict(e.attrib)
            for i,e in enumerate(root.iter())}


def main():
    current=(ROOT/PATH).read_bytes()
    prior=subprocess.check_output(["git","show",f"origin/{BASE}:{PATH}"],cwd=ROOT)
    b=parse(prior);c=parse(current)
    assert b.keys()==c.keys(),"XML nodes were added/removed/reordered"
    changes=[]
    for key,old in b.items():
        new=c[key]
        for attr in set(old)|set(new):
            if old.get(attr)!=new.get(attr):
                changes.append((key[1],attr,old.get(attr),new.get(attr)))
    assert len(changes)==2,changes
    assert {(x[0],x[1],x[2],x[3]) for x in changes} == {
        ("SUPPORT_SCENE_OPTIMIZER","value","true","false"),
        ("SUPPORT_PHOTO_NIGHT","value","true","false"),
    },changes
    # Byte-level guarantee: no unrelated whitespace, XML nodes, or mode changes.
    expected=prior
    for name in sorted(flags):
        lines=expected.splitlines(keepends=True)
        hits=[i for i,x in enumerate(lines) if f'name="{name}"'.encode() in x]
        assert len(hits)==1
        lines[hits[0]]=lines[hits[0]].replace(b'value="true"',b'value="false"')
        expected=b"".join(lines)
    assert current==expected,"More than two string replacements were made"
    for token in (
        b'name="SHOOTING_MODE_PHOTO" back="PHOTO" front="PHOTO" enable="true"',
        b'name="SHOOTING_MODE_VIDEO" back="VIDEO" front="VIDEO" enable="true"',
        b'name="BACK_CAMERA_RECORDING_DEFAULT_RESOLUTION" value="1920x1080"',
        b'name="FRONT_CAMERA_RECORDING_DEFAULT_RESOLUTION" value="1920x1080"',
    ):
        assert token in current,"Camera photo/video feature unexpectedly altered"
    print("PASS: only two hypothesis-test flags changed; photo, Video6 and remaining XML bytes preserved")
    print("NOT PROOF: physical 4–5 second shutter latency fixed; requires A/B test on device")


if __name__=="__main__":main()
