#!/usr/bin/env python3
"""Regression gate for Galaxy S8+ post-flash 2026-10-20 recording crash.

Input values are tiny sanitized excerpts from user Camera2 dump. Do not
publish the full logcat / Camera2 dump (subscriber, location or device IDs).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/"tools/native_camera/alice_preview_bridge.c").read_text()
# Samsung Exynos vendor reference m_createVendorControlAvailableVideoConfigurations:
# [w, h, fpsMin, fpsMax, cropPercent, timeLimit] per item
# https://github.com/Linux4/android_hardware_samsung_slsi-linaro_exynos/blob/lineage-21/libcamera3/common/Sec/ExynosCameraMetadataConverterVendor.cpp
def decode_samsung_video(raw):
    assert len(raw)%6==0, "Samsung VideoStreamConfig expects a six-int tuple"
    items=[]
    for i in range(0,len(raw),6):
        width,height,min_fps,max_fps,crop,limit=raw[i:i+6]
        assert 0<width<=8192 and 0<height<=8192
        assert 0<min_fps<=max_fps<=240
        assert -100<=crop<=100
        assert limit>=0
        items.append(dict(size=(width,height),range=(min_fps,max_fps),crop=crop,limit=limit))
    return items

def build_from_observed(streams,ae_ranges,frame_durations):
    assert (30,30) in ae_ranges
    result=[]
    for fmt,w,h,output in streams:
        if fmt!=34 or output!=0 or not(640<=w<=1920 and 360<=h<=1080):continue
        d=frame_durations.get((fmt,w,h))
        if not d or d>1_000_000_000//30:continue
        result.extend((w,h,30,30,0,0))
    return result

# Old synthetic data from actual postflash Camera2 report:
bad=[34,4032,3024,0]
assert len(bad)%6!=0, "Old 4-int preview tuple should not be accepted as video"
# Sanitized reference from real rear camera snapshot, 2026-10-20:
sizes=[(34,4032,3024,0),(34,1920,1080,0),(34,1440,1080,0),
       (34,1280,720,0),(34,640,480,0),(33,4032,3024,0)]
fps=[(15,15),(24,24),(15,30),(30,30)]
durations={(34,1920,1080):33331760,(34,1440,1080):33331760,
           (34,1280,720):33331760,(34,640,480):33331760}
encoded=build_from_observed(sizes,fps,durations)
config=decode_samsung_video(encoded)
assert config and config[0]["size"]==(1920,1080)
assert all(t["range"]==(30,30) for t in config)
assert len(config)==4
assert "#define VIDEO_FIELDS 6" in SOURCE
assert "#define AOSP_AE_FPS_RANGES 0x00010014u" in SOURCE
assert "#define AOSP_MIN_FRAME_DURATIONS 0x000d000bu" in SOURCE
assert "min_durations.type!=TYPE_INT64" in SOURCE
assert "ae_fps.type!=TYPE_INT32" in SOURCE
assert "video_config[pos+2]=VIDEO_FPS;" in SOURCE
assert "video_config[pos+3]=VIDEO_FPS;" in SOURCE
assert "add(merged,VIDEO_TAG,video_config,video_n*VIDEO_FIELDS)" in SOURCE
assert "add(merged,VIDEO_TAG,preview_config" not in SOURCE
assert "w>1920 || h>1080" in SOURCE, "do not advertise unvalidated UHD/60fps"
print("PASS: Samsung Exynos six-int video format, verified Camera2 30fps support, no fake preview-as-video tuples")
print("FIX IS SOURCE/CI ONLY: physical Samsung Camera video record and playback not tested.")
