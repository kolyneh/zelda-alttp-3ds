#!/usr/bin/env python3
"""Fetch SHA-256-pinned library sources and Linux packaging tools."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
import zipfile
ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def open_url(url):
    return urlopen(Request(url, headers={'User-Agent': 'zelda3-3ds-cn-build'}), timeout=60)


def fetch(entry, directory):
    name, digest = entry['file'], entry['sha256']
    if Path(name).name != name or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Invalid pinned input filename or SHA-256')
    if not entry['url'].startswith('https://'):
        raise ValueError('Build input URL must use HTTPS')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if path.is_file() and sha256(path) == digest:
        return path
    temporary = Path(str(path) + '.tmp')
    try:
        with open_url(entry['url']) as response, temporary.open('wb') as output:
            size = 0
            while data := response.read(1024 * 1024):
                size += len(data)
                if size > 64 * 1024 * 1024:
                    raise ValueError(f'Build input exceeds size limit: {name}')
                output.write(data)
        if sha256(temporary) != digest:
            raise ValueError(f'SHA-256 mismatch for {name}')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Verified {name}: {digest}')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, default=ROOT / 'build-3ds/downloads')
    parser.add_argument('--tools', type=Path, default=ROOT / 'build-3ds/tools')
    parser.add_argument('--libraries-only', action='store_true')
    args = parser.parse_args()
    try:
        sources = json.loads((ROOT / 'platform/3ds/update-dependencies/sources.json').read_text())
        for entry in sources:
            if entry['file'].endswith('.patch'):
                local = ROOT / 'platform/3ds/update-dependencies' / entry['file']
            elif entry['file'] == 'cacert.pem':
                local = ROOT / 'platform/3ds/romfs/update-ca.pem'
            else:
                fetch(entry, args.downloads)
                continue
            if sha256(local) != entry['sha256']:
                raise ValueError(f'Bundled input checksum mismatch: {local}')
        if not args.libraries_only:
            args.tools.mkdir(parents=True, exist_ok=True)
            lock = json.loads((ROOT / 'platform/3ds/build-tools.lock.json').read_text())
            for entry in lock['tools']:
                archive = fetch(entry, args.downloads)
                if Path(entry['output']).name != entry['output']:
                    raise ValueError('Tool output must be a filename')
                with zipfile.ZipFile(archive) as file:
                    data = file.read(entry['member'])
                output = args.tools / entry['output']
                output.write_bytes(data); output.chmod(0o755)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f'Build input preparation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
