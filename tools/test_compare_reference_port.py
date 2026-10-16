#!/usr/bin/env python3
"""Regression tests for the read-only port comparator."""
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "port_cmp", Path(__file__).with_name("compare_reference_port.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as temp:
    a, b = Path(temp) / "a", Path(temp) / "b"
    for p in (a, b):
        (p / "lib64/hw").mkdir(parents=True)
        (p / "etc/init").mkdir(parents=True)
    (a / "lib64/hw/camera.universal8895.so").write_bytes(b"old")
    (b / "lib64/hw/camera.universal8895.so").write_bytes(b"new")
    (a / "etc/init/init.vendor.rilcommon.rc").write_bytes(b"same")
    (b / "etc/init/init.vendor.rilcommon.rc").write_bytes(b"same")
    camera = mod.compare(a, b, "camera")
    radio = mod.compare(a, b, "radio")
    assert camera["differences"][0]["status"] == "different"
    assert len(camera["differences"]) == 1
    assert len(radio["differences"]) == 0
    print("PASS: reference camera/radio SHA256 comparison")
