#!/usr/bin/env python3
"""Verify embedded resources and stage ROM-free 3DS distributables."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TITLE_ID = 0x0004000005A13E00
VERSION = '3.2.2'
ALLOWED = {'zelda3_assets.bps', 'zelda3.ini', 'zelda3_cn.pack',
           'chinese-font-notice.txt', 'chinese-font-OFL.txt', 'update-ca.pem'}
RELEASE_LICENSES = {
    'engine-LICENSE.txt': 'vendor/zelda3/LICENSE.txt',
    'SDL2-LICENSE.txt': 'app/jni/SDL2/LICENSE.txt',
    'curl-LICENSE.txt': 'platform/3ds/update-dependencies/LICENSE-curl.txt',
    'mbedTLS-LICENSE.txt': 'platform/3ds/update-dependencies/LICENSE-mbedTLS.txt',
    'Jansson-LICENSE.txt': 'platform/3ds/update-dependencies/LICENSE-Jansson.txt',
}


def part(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise ValueError('Truncated package section')
    return data[offset:offset + size]


def number(data, fmt, offset):
    return struct.unpack(fmt, part(data, offset, struct.calcsize(fmt)))[0]


def align(value, boundary):
    return (value + boundary - 1) & -boundary


def romfs_files(data):
    header = struct.unpack('<10I', part(data, 0, 40))
    if header[0] != 40:
        raise ValueError('Invalid RomFS header')
    root = part(data, header[3], header[4])
    if len(root) < 24 or number(root, '<I', 8) != 0xffffffff:
        raise ValueError('Only flat release RomFS is supported')
    table = part(data, header[7], header[8])
    files, seen = {}, set()
    offset = number(root, '<I', 12)
    while offset != 0xffffffff:
        if offset in seen:
            raise ValueError('RomFS file list cycle')
        seen.add(offset)
        parent, sibling, start, size, _, length = struct.unpack('<IIQQII', part(table, offset, 32))
        if parent != 0 or length % 2:
            raise ValueError('Invalid RomFS file entry')
        try:
            name = part(table, offset + 32, length).decode('utf-16le')
        except UnicodeError as error:
            raise ValueError('Invalid RomFS name') from error
        if not name or name in files or '/' in name or '\\' in name or '\0' in name:
            raise ValueError('Invalid or duplicate RomFS filename')
        files[name] = part(data, header[9] + start, size)
        offset = sibling
    return files


def three_dsx_files(data):
    if part(data, 0, 4) != b'3DSX' or number(data, '<H', 4) < 44:
        raise ValueError('Missing extended 3DSX header')
    return romfs_files(data[number(data, '<I', 40):])


def cia_files(data):
    header = number(data, '<I', 0)
    cert, ticket, tmd_size = (number(data, '<I', i) for i in (8, 12, 16))
    content_size = number(data, '<Q', 24)
    tmd_offset = align(align(align(header, 64) + cert, 64) + ticket, 64)
    tmd = part(data, tmd_offset, tmd_size)
    if number(tmd, '>I', 0) != 0x10004:
        raise ValueError('Unsupported TMD signature format')
    if number(tmd, '>Q', 0x18c) != TITLE_ID or number(tmd, '>H', 0x1de) != 1:
        raise ValueError('Wrong CIA title ID or content count')
    size = number(tmd, '>Q', 0xb0c)
    if number(tmd, '>H', 0xb0a) & 1 or size != content_size:
        raise ValueError('Encrypted or inconsistent CIA content')
    ncch = part(data, align(tmd_offset + tmd_size, 64), size)
    if hashlib.sha256(ncch).digest() != part(tmd, 0xb14, 32):
        raise ValueError('CIA content SHA-256 mismatch')
    if part(ncch, 0x100, 4) != b'NCCH' or number(ncch, '<Q', 0x118) != TITLE_ID:
        raise ValueError('Wrong NCCH identity')
    if not number(ncch, '<B', 0x18f) & 4:
        raise ValueError('Encrypted NCCH is unsupported')
    shift = number(ncch, '<B', 0x18e)
    if shift > 8:
        raise ValueError('Invalid NCCH block size')
    unit = 512 << shift
    romfs = part(ncch, number(ncch, '<I', 0x1b0) * unit,
                 number(ncch, '<I', 0x1b4) * unit)
    if part(romfs, 0, 4) != b'IVFC':
        raise ValueError('Missing IVFC RomFS')
    block_log = number(romfs, '<I', 0x4c)
    if block_log > 24:
        raise ValueError('Invalid IVFC block size')
    offset = align(0x60 + number(romfs, '<I', 8), 1 << block_log)
    return romfs_files(part(romfs, offset, number(romfs, '<Q', 0x44)))


def verify_files(files, expected):
    if set(files) != ALLOWED or set(expected) != ALLOWED:
        raise ValueError('Unexpected or missing release RomFS files')
    for name in ALLOWED:
        if files[name] != expected[name]:
            raise ValueError(f'Embedded resource mismatch: {name}')


def main():
    game = ROOT / 'build-3ds/game'
    expected = {p.name: p.read_bytes() for p in (game / 'romfs').iterdir() if p.is_file()}
    packages = [game / f'zelda3-3ds-v{VERSION}.{ext}' for ext in ('3dsx', 'cia')]
    for package, reader in zip(packages, (three_dsx_files, cia_files)):
        verify_files(reader(package.read_bytes()), expected)
    release = ROOT / 'build-3ds/release'
    if release.exists():
        shutil.rmtree(release)
    release.mkdir(parents=True)
    for package in packages:
        shutil.copy2(package, release)
    for output, source in RELEASE_LICENSES.items():
        shutil.copy2(ROOT / source, release / output)
    for name in ('chinese-font-notice.txt', 'chinese-font-OFL.txt'):
        (release / name).write_bytes(expected[name])
    metadata = {
        'version': VERSION, 'title_id': f'{TITLE_ID:016x}',
        'commit': subprocess.check_output(
            ['git', '-c', 'safe.directory=' + str(ROOT), 'rev-parse', 'HEAD'],
            cwd=ROOT, text=True).strip(),
        'engine': json.loads((ROOT / 'platform/3ds/engine.lock.json').read_text()),
        'build_tools': json.loads((ROOT / 'platform/3ds/build-tools.lock.json').read_text()),
        'romfs_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in sorted(expected.items())},
    }
    (release / 'build-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    sums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                   for p in sorted(release.iterdir()))
    (release / 'SHA256SUMS').write_text(sums)
    print(f'Verified CIA title ID, content hashes, and embedded resources: {release}')


if __name__ == '__main__':
    main()
