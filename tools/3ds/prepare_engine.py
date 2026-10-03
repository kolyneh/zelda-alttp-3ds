#!/usr/bin/env python3
"""Prepare the pinned sxunix engine with the reviewed Nintendo 3DS patch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def prepare(source, output, lock_path):
    if not (source / 'src/main.c').is_file():
        raise ValueError('Missing engine dependency; run git submodule update --init --recursive')
    lock = json.loads(lock_path.read_text())
    result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != lock['commit']:
        raise ValueError('Engine commit does not match engine.lock.json; run git submodule update --init --recursive')
    result = subprocess.run(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'],
                            capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise ValueError('Engine dependency has local changes; restore the pinned submodule before preparing')
    if output == source or source in output.parents:
        raise ValueError('Output must be outside the engine dependency')
    patches = []
    for entry in lock['patches']:
        patch = ROOT / entry['path']
        if hashlib.sha256(patch.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Engine patch checksum mismatch: ' + str(patch))
        patches.append(patch)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.engine-stage-', dir=output.parent) as temp:
        stage = Path(temp) / 'engine'
        stage.mkdir()
        for name in ('src', 'snes', 'third_party'):
            shutil.copytree(source / name, stage / name)
        # Upstream source has CRLF; historical port edits mix LF and CRLF.
        # Canonicalize the generated C sources before applying the LF patch.
        for section in ('src', 'snes'):
            for path in (stage / section).rglob('*'):
                if path.is_file():
                    data = path.read_bytes()
                    if b'\0' not in data:
                        path.write_bytes(data.replace(b'\r\n', b'\n'))
        shutil.copyfile(source / 'LICENSE.txt', stage / 'LICENSE.txt')
        # Treat the staging directory as a plain source tree. Otherwise Git
        # discovers the enclosing worktree and silently skips relative paths.
        patch_env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(stage.parent))
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
            patch_env.pop(key, None)
        for patch in patches:
            result = subprocess.run(['git', 'apply', '--no-index', '--check', str(patch)],
                                    cwd=stage, env=patch_env, capture_output=True, text=True)
            if result.returncode:
                raise ValueError('Engine patch cannot be applied: ' + result.stderr.strip())
            subprocess.run(['git', 'apply', '--no-index', str(patch)], cwd=stage, env=patch_env, check=True)
        (stage / '.engine-origin.json').write_text(json.dumps(lock, indent=2) + '\n')
        backup = Path(temp) / 'previous'
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    print('Prepared sxunix ' + lock['commit'][:12] + ' with Nintendo 3DS adaptations')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'vendor/zelda3')
    parser.add_argument('--output', type=Path, default=ROOT / 'build-3ds/engine')
    parser.add_argument('--lock', type=Path, default=ROOT / 'platform/3ds/engine.lock.json')
    args = parser.parse_args()
    try:
        prepare(args.source.resolve(), args.output.resolve(), args.lock.resolve())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
