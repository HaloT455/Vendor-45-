#!/usr/bin/env python3
"""Repack the Test7 vendor with original EROFS metadata; verify the result."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

from inventory_erofs import inventory, readable_tree, sha256

ROOT = Path(__file__).resolve().parents[1]


def verify_source(manifest, allow_changes=False):
    root = ROOT / 'vendor'
    readable_tree(root)
    expected = {e['path']: e for e in manifest['entries']}
    actual = {'.'}
    for current, dirs, files in os.walk(root):
        for name in dirs + files:
            actual.add((Path(current)/name).relative_to(root).as_posix())
    assert actual == set(expected), f'Paths differ: {actual ^ set(expected)}; update the manifest intentionally'
    changed = []
    for rel, e in expected.items():
        p = root / rel
        if e['type'] == 'file':
            assert p.is_file() and not p.is_symlink(), rel
            if p.stat().st_size != e['size'] or sha256(p) != e['sha256']:
                changed.append(rel)
        elif e['type'] == 'symlink':
            assert p.is_symlink() and os.readlink(p) == e['target'], rel
        else:
            assert p.is_dir() and not p.is_symlink(), rel
    assert allow_changes or not changed, f'File content changed: {changed}; use --allow-file-changes on a work branch'
    return changed


def tar_source(manifest, output):
    hardlinks = {}
    with tarfile.open(output, 'w', format=tarfile.PAX_FORMAT) as tar:
        for e in manifest['entries']:
            p = ROOT / 'vendor' / e['path']
            info = tarfile.TarInfo(e['path'])
            info.mode, info.uid, info.gid = e['mode'], e['uid'], e['gid']
            info.mtime = e['mtime']
            if e['mtime_nsec']:
                info.pax_headers['mtime'] = f"{e['mtime']}.{e['mtime_nsec']:09d}"
            info.pax_headers.update({f'SCHILY.xattr.{k}': base64.b64decode(v).decode('utf-8')
                                     for k, v in e['xattrs'].items()})
            if e['type'] == 'directory':
                info.type = tarfile.DIRTYPE
            elif e['type'] == 'symlink':
                info.type, info.linkname = tarfile.SYMTYPE, e['target']
            elif e['nlink'] > 1 and e['nid'] in hardlinks:
                info.type, info.linkname = tarfile.LNKTYPE, hardlinks[e['nid']]
            else:
                info.size = p.stat().st_size
                hardlinks[e['nid']] = e['path']
                with p.open('rb') as source:
                    tar.addfile(info, source)
                continue
            tar.addfile(info)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, default=ROOT/'.tools/erofs/usr/bin')
    p.add_argument('--output', type=Path, default=ROOT/'out/vendor.img')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--allow-file-changes', action='store_true')
    p.add_argument('--max-image-bytes', type=int, default=None,
                   help='Research experiment only: never use as evidence of device partition size')
    a = p.parse_args()
    manifest = json.loads((ROOT/'metadata/vendor-image-manifest.json').read_text())
    changed = verify_source(manifest, a.allow_file_changes)
    if a.verify_only:
        print(json.dumps({'verified':True, 'entries':len(manifest['entries']), 'changed_files':changed}))
        return
    branch = subprocess.check_output(['git','branch','--show-current'], cwd=ROOT, text=True).strip()
    assert branch.startswith('work/'), 'Build on a work/* branch; preserve the baseline'
    tools = a.tools.resolve()
    version = subprocess.check_output([str(tools/'mkfs.erofs'), '-V'], text=True)
    assert '1.8.6' in version, 'Use the pinned erofs-utils 1.8.6 toolchain'
    output = a.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assert not output.exists(), f'Output already exists: {output}; choose another --output'
    s = manifest['superblock']
    with tempfile.TemporaryDirectory(prefix='vendor-build-', dir=output.parent) as temp:
        temp = Path(temp)
        archive = temp/'vendor.tar'
        tar_source(manifest, archive)
        command = [str(tools/'mkfs.erofs'), '--tar=f', '-zlz4hc,level=12',
                   '-b'+str(s['block_size']), '-C4096',
                   '-E', '^xattr-name-filter,^ztailpacking,^fragments',
                   '-T'+str(s['build_time']), '--mkfs-time', '-U'+s['uuid'],
                   '--workers=4', '--quiet', str(output), str(archive)]
        subprocess.run(command, check=True)
        extracted = temp/'check'
        subprocess.run([str(tools/'fsck.erofs'), '--no-preserve-owner', '--no-preserve-perms',
                        '--extract='+str(extracted), str(output)], check=True)
        rebuilt = inventory(output, extracted)
        old = {e['path']:e for e in manifest['entries']}
        new = {e['path']:e for e in rebuilt['entries']}
        assert old.keys() == new.keys(), 'Rebuilt paths differ'
        for rel, e in old.items():
            n = new[rel]
            keys = ['type','mode','uid','gid','mtime','mtime_nsec','nlink','xattrs']
            if e['type'] == 'symlink':
                keys += ['target','size']
            for key in keys:
                assert e[key] == n[key], f'Metadata differs: {rel} {key}'
            if e['type'] == 'file':
                assert n['sha256'] == sha256(ROOT/'vendor'/rel), f'Data differs: {rel}'
        for key in ['block_size','build_time','build_time_nsec','feature_compat','feature_incompat','uuid']:
            assert s[key] == rebuilt['superblock'][key], f'Superblock differs: {key}'
        image_limit = a.max_image_bytes if a.max_image_bytes is not None else manifest['source_image_bytes']
        assert image_limit >= manifest['source_image_bytes'], 'Experimental limit must not shrink baseline'
        assert output.stat().st_size <= image_limit, f'Image exceeds configured size limit: {image_limit}'
        report = {'verified':True, 'entries':len(old), 'changed_files':changed,
                  'source_image_sha256':manifest['source_image_sha256'],
                  'rebuilt_image_sha256':rebuilt['source_image_sha256'],
                  'rebuilt_image_bytes':output.stat().st_size,
                  'byte_identical':rebuilt['source_image_sha256'] == manifest['source_image_sha256'],
                  'runtime_tested':False, 'mkfs_command':command[:-2]+['OUTPUT','SOURCE_TAR']}
        output.with_suffix('.report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
