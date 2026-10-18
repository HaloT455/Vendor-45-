#!/usr/bin/env python3
"""Read-only Samsung Camera ACCESS_SYSTEM_KEY_DISPATCHING preflight (ADB)."""
import argparse
import datetime
import json
import re
import subprocess
from pathlib import Path
PERMISSION='com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING'
PACKAGE='com.sec.android.app.camera'

def get_permission_section(dump):
    m=re.search(r'^\s*Permission\s*\['+re.escape(PERMISSION)+r'\]\s*\([^\n]*\):?',dump,re.M)
    return '\n'.join(dump[m.start():].splitlines()[:13]) if m else None

def analyze(dump, package_dump):
    perm=get_permission_section(dump)
    level=re.search(r'\bprot=([^\s]+)',perm or '')
    mode=level.group(1) if level else None
    path=re.search(r'^\s*codePath=(\S+)',package_dump,re.M)
    flags=re.search(r'^\s*privateFlags=\[([^\n]*)',package_dump,re.M)
    requested=bool(re.search(r'^\s*'+re.escape(PERMISSION)+r'\s*$',package_dump,re.M))
    section=package_dump.split('    install permissions:',1)[-1].split('    User 0:',1)[0] if '    install permissions:' in package_dump else ''
    grant=re.search(r'^\s*'+re.escape(PERMISSION)+r': granted=(true|false)',section,re.M)
    granted=grant.group(1)=='true' if grant else False
    if granted: status='already_granted_check_runtime_uid_or_framework_enforcement'
    elif not perm: status='permission_not_declared_in_ROM_privapp_allowlist_cannot_fix_by_itself'
    elif not mode: status='permission_protection_level_unavailable_need_full_definition'
    elif 'privileged' in mode or 'signatureOrSystem' in mode:
        status='system_privapp_possible_only_after_complete_privapp_allowlist_audit_and_backup'
    else: status='system_privapp_alone_not_sufficient_consider_app_or_framework_compatibility_patch'
    return {'package':PACKAGE,'permission':PERMISSION,'package_code_path':path.group(1) if path else None,
      'privileged_app':bool(flags and 'PRIVILEGED' in flags.group(1)),'permission_requested':requested,
      'permission_granted':granted,'permission_protection_level':mode,'permission_definition_excerpt':perm,
      'next_step':status,'automatic_fix_applied':False}

def adb(*args):
    r=subprocess.run(['adb','-d',*args],capture_output=True,text=True,errors='replace')
    if r.returncode: raise RuntimeError(f"adb -d {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--selftest',action='store_true')
    args=ap.parse_args()
    if args.selftest:
        pkg='''  codePath=/data/app/example
    privateFlags=[ ALLOW_AUDIO_PLAYBACK_CAPTURE ]
    requested permissions:
      com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING
    install permissions:
      android.permission.INTERNET: granted=true
    User 0: installed=true
'''
        dump='''Permission [com.samsung.android.permission.ACCESS_SYSTEM_KEY_DISPATCHING] (123456):
  sourcePackage=android
  uid=1000 gids=[] type=0 prot=signature|privileged
  perm=PermissionInfo{}
'''
        r=analyze(dump,pkg)
        assert r['permission_protection_level']=='signature|privileged'
        assert r['next_step'].startswith('system_privapp_possible')
        assert not r['privileged_app'] and r['permission_requested']
        assert analyze('',pkg)['next_step'].startswith('permission_not_declared')
        assert analyze(dump.replace('signature|privileged','signature'),pkg)['next_step'].startswith('system_privapp_alone_not_sufficient')
        print('PASS 3/3 permission preflight contract tests')
        return
    print('Collecting Samsung Camera permission definition; READ ONLY...',flush=True)
    result=analyze(adb('shell','dumpsys','package'),adb('shell','dumpsys','package',PACKAGE))
    out=Path.home()/'Downloads'/f"ALICE_KEY_PERMISSION_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('REPORT:',out)
    print('No permission grants, APK replacements or vendor changes made.')
if __name__=='__main__': main()
