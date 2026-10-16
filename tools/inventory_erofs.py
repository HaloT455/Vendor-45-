#!/usr/bin/env python3
"""Inventory legacy EROFS metadata directly; hash data from fsck extraction.

Format reference: erofs-utils v1.8.6 include/erofs_fs.h.
Rejects unsupported layouts/features instead of guessing their metadata.
"""
import argparse
import base64
import hashlib
import json
import mmap
import os
from pathlib import Path
import stat
import struct
import uuid


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


class Erofs:
    def __init__(self, path):
        self.file = open(path, 'rb')
        self.data = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.path = Path(path)
        s = 1024
        assert self.u('I', s) == 0xE0F5E1E2, 'Not a raw EROFS image'
        self.block = 1 << self.u('B', s + 12)
        self.root = self.u('H', s + 14)
        self.meta = self.u('I', s + 40) * self.block
        self.xattr = self.u('I', s + 44) * self.block
        self.epoch = self.u('Q', s + 24)
        self.ns = self.u('I', s + 32)
        self.super = {
            'block_size': self.block, 'inode_count': self.u('Q', s + 16),
            'build_time': self.epoch, 'build_time_nsec': self.ns,
            'blocks': self.u('I', s + 36),
            'feature_compat': self.u('I', s + 8),
            'feature_incompat': self.u('I', s + 80),
            'uuid': str(uuid.UUID(bytes=bytes(self.data[s+48:s+64]))),
        }
        assert self.super['feature_incompat'] & ~1 == 0, 'Unsupported EROFS features'

    def u(self, fmt, offset):
        return struct.unpack_from('<' + fmt, self.data, offset)[0]

    def xentry(self, offset):
        nl, idx, vl = struct.unpack_from('<BBH', self.data, offset)
        prefixes = {1: 'user.', 2: 'system.posix_acl_access',
                    3: 'system.posix_acl_default', 4: 'trusted.',
                    5: 'lustre.', 6: 'security.'}
        assert idx in prefixes, 'Unsupported xattr namespace'
        name = prefixes[idx] + self.data[offset+4:offset+4+nl].decode()
        value = bytes(self.data[offset+4+nl:offset+4+nl+vl])
        return name, base64.b64encode(value).decode(), (4 + nl + vl + 3) & ~3

    def inode(self, nid):
        pos = self.meta + nid * 32
        fmt, icount, mode = struct.unpack_from('<HHH', self.data, pos)
        assert fmt < 16
        extended = bool(fmt & 1)
        inode_size = 64 if extended else 32
        xsize = 12 + 4 * (icount - 1) if icount else 0
        row = {'nid': nid, 'mode': stat.S_IMODE(mode),
               'type': {stat.S_IFDIR: 'directory', stat.S_IFREG: 'file',
                        stat.S_IFLNK: 'symlink'}[stat.S_IFMT(mode)],
               'size': self.u('Q' if extended else 'I', pos+8),
               'uid': self.u('I' if extended else 'H', pos+24),
               'gid': self.u('I', pos+28) if extended else self.u('H', pos+26),
               'mtime': self.u('Q', pos+32) if extended else self.epoch,
               'mtime_nsec': self.u('I', pos+40) if extended else self.ns,
               'nlink': self.u('I', pos+44) if extended else self.u('H', pos+6),
               'xattrs': {}}
        if xsize:
            start = pos + inode_size
            shared_count = self.u('B', start+4)
            for i in range(shared_count):
                shared_id = self.u('I', start+12+i*4)
                k, v, _ = self.xentry(self.xattr + shared_id*4)
                row['xattrs'][k] = v
            cur = start + 12 + shared_count*4
            while cur < start + xsize:
                k, v, length = self.xentry(cur)
                assert k not in row['xattrs']
                row['xattrs'][k] = v
                cur += length
            assert cur == start + xsize
        return row, (fmt >> 1) & 7, self.u('I', pos+16), pos+inode_size+xsize

    def flat(self, row, layout, address, inline):
        assert layout in (0, 2), 'Unsupported directory/symlink layout'
        size = row['size']
        whole = size if layout == 0 else size // self.block * self.block
        return bytes(self.data[address*self.block:address*self.block+whole]) + (
            bytes(self.data[inline:inline+size-whole]) if layout == 2 else b'')

    def walk(self):
        entries = []
        seen_dirs = set()
        def visit(nid, path):
            row, layout, addr, inline = self.inode(nid)
            row['path'] = path
            entries.append(row)
            if row['type'] == 'symlink':
                row['target'] = self.flat(row, layout, addr, inline).decode()
            if row['type'] != 'directory':
                return
            assert nid not in seen_dirs, 'Directory cycle'
            seen_dirs.add(nid)
            data = self.flat(row, layout, addr, inline)
            for start in range(0, len(data), self.block):
                block = data[start:start+self.block]
                count = struct.unpack_from('<H', block, 8)[0] // 12
                for i in range(count):
                    child, off, _, _ = struct.unpack_from('<QHBB', block, i*12)
                    end = struct.unpack_from('<H', block, (i+1)*12+8)[0] if i+1 < count else len(block)
                    name = block[off:end].split(b'\0', 1)[0].decode()
                    if name in ('.', '..'):
                        continue
                    assert name and '/' not in name
                    visit(child, name if path == '.' else path+'/'+name)
        visit(self.root, '.')
        assert len(set(e['nid'] for e in entries)) == self.super['inode_count']
        assert len(set(e['path'] for e in entries)) == len(entries)
        return sorted(entries, key=lambda e: e['path'])


def readable_tree(root):
    for current, directories, _ in os.walk(root):
        os.chmod(current, 0o755)
        for name in directories:
            p = Path(current, name)
            if not p.is_symlink():
                os.chmod(p, 0o755)


def inventory(image, tree):
    fs = Erofs(image)
    entries = fs.walk()
    readable_tree(tree)
    for e in entries:
        p = Path(tree, e['path'])
        if e['type'] == 'file':
            assert p.is_file() and not p.is_symlink() and p.stat().st_size == e['size'], e['path']
            e['sha256'] = sha256(p)
        elif e['type'] == 'symlink':
            assert p.is_symlink() and os.readlink(p) == e['target'], e['path']
        else:
            assert p.is_dir() and not p.is_symlink(), e['path']
    return {'schema': 1, 'source_image_sha256': sha256(image),
            'source_image_bytes': Path(image).stat().st_size,
            'superblock': fs.super, 'entries': entries}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('image', type=Path)
    p.add_argument('tree', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    result = inventory(a.image, a.tree)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'entries':len(result['entries']), 'image_sha256':result['source_image_sha256']}))
