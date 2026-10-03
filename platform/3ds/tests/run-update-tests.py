#!/usr/bin/env python3
"""Run the updater's host harnesses with a native Jansson prefix."""
import argparse
import pathlib
import sys
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--jansson-prefix', type=pathlib.Path, required=True)
parser.add_argument('--live-check', action='store_true')
parser.add_argument('--jansson-library', type=pathlib.Path, help='Override static archive path for multiarch host prefixes')
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[3]
tests = root / 'platform/3ds/tests'
source = root / 'platform/3ds/source'
prefix = args.jansson_prefix.resolve()
library = args.jansson_library.resolve() if args.jansson_library else prefix / 'lib/libjansson.a'
with tempfile.TemporaryDirectory(prefix='lod-updater-test-') as temporary:
    work = pathlib.Path(temporary)
    common = ['cc', '-std=c11', '-I' + str(prefix / 'include'), '-I' + str(source)]
    manifest = work / 'manifest-test'
    subprocess.run(common + ['-fsanitize=address,undefined',
        str(tests / 'update_manifest_test.c'), str(source / 'update_manifest.c'),
        str(library), '-o', str(manifest)], check=True)
    subprocess.run([str(manifest)], cwd=work, check=True)
    host = work / 'updater-test'
    version = '3.2.1'
    linker = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--gc-sections', '-lcrypto']
    subprocess.run(common + [f'-DZELDA3_3DS_VERSION="{version}"', '-Wno-deprecated-declarations',
        '-fsanitize=address,undefined', '-ffunction-sections', '-fdata-sections', '-I' + str(tests / 'update_host'),
        str(tests / 'updater_host_test.c'), str(source / 'update_manifest.c'),
        str(library), '-lcurl'] + linker + ['-o', str(host)], check=True)
    (work / 'sdmc:/3ds/Zelda 3DS/update').mkdir(parents=True)
    (work / 'romfs:').mkdir()
    shutil.copyfile(root / 'platform/3ds/romfs/update-ca.pem', work / 'romfs:/update-ca.pem')
    subprocess.run([str(host)] + (['--live-check'] if args.live_check else []), cwd=work, check=True)
