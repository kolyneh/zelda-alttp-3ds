import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/3ds/prepare_engine.py'
SOURCE = ROOT / 'vendor/zelda3'
if not SOURCE.exists():
    SOURCE = ROOT.parent / 'sxunix-zelda3'


def lock_data():
    path = ROOT / 'platform/3ds/engine.lock.json'
    if path.exists():
        return json.loads(path.read_text())
    return {'commit': 'eb61ac5e5224580b126d00203dfd2da2ede022d1', 'patches': []}


class EnginePreparationTests(unittest.TestCase):
    def run_prepare(self, source, output, lock=None):
        cmd = [sys.executable, str(SCRIPT), '--source', str(source), '--output', str(output)]
        if lock:
            cmd += ['--lock', str(lock)]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_missing_submodule_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as t:
            result = self.run_prepare(Path(t) / 'missing', Path(t) / 'out')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('submodule update --init', result.stderr)

    def test_preparation_preserves_3ds_and_chinese_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'engine'
            result = self.run_prepare(SOURCE, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('VWF_RenderChinese', (out / 'src/messaging.c').read_text())
            self.assertIn('Platform3DS_PresentTopFrame', (out / 'src/main.c').read_text())
            self.assertIn('ZeldaShutdownPpuWorker', (out / 'src/zelda_rtl.h').read_text())
            def hashes():
                return {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in out.rglob('*') if p.is_file()}
            before = hashes()
            self.assertEqual(self.run_prepare(SOURCE, out).returncode, 0)
            self.assertEqual(before, hashes())
            self.assertTrue((out / 'third_party/opus-1.3.1-stripped/opus_decoder_amalgam.c').exists())

    def test_wrong_commit_does_not_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            lock = lock_data()
            lock['commit'] = '0' * 40
            (t / 'lock.json').write_text(json.dumps(lock))
            out = t / 'out'; out.mkdir(); (out / 'keep').write_text('original')
            result = self.run_prepare(SOURCE, out, t / 'lock.json')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('commit', result.stderr)
            self.assertEqual((out / 'keep').read_text(), 'original')

    def test_output_inside_worktree_matches_external_output(self):
        build = ROOT / 'build-3ds'
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as inside, tempfile.TemporaryDirectory() as outside:
            a, b = Path(inside) / 'engine', Path(outside) / 'engine'
            self.assertEqual(self.run_prepare(SOURCE, a).returncode, 0)
            self.assertEqual(self.run_prepare(SOURCE, b).returncode, 0)
            self.assertEqual((a / 'snes/ppu.h').read_bytes(), (b / 'snes/ppu.h').read_bytes())
            self.assertEqual({str(p.relative_to(a)) for p in a.rglob('*')},
                             {str(p.relative_to(b)) for p in b.rglob('*')})

    def test_modified_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            source = t / 'source'
            subprocess.run(['git', 'clone', '--shared', '--quiet', str(SOURCE), str(source)], check=True)
            with (source / 'src/main.c').open('a') as file:
                file.write('\n/* local modification */\n')
            result = self.run_prepare(source, t / 'out')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('local changes', result.stderr)

    def test_bad_patch_fails_without_replacing_output(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            lock = lock_data()
            patch = t / 'bad.patch'
            patch.write_text('diff --git a/src/main.c b/src/main.c\n--- a/src/main.c\n+++ b/src/main.c\n@@ -1 +1 @@\n-impossible line\n+replacement\n')
            lock['patches'] = [{'path': str(patch), 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest()}]
            (t / 'lock.json').write_text(json.dumps(lock))
            out = t / 'out'; out.mkdir(); (out / 'keep').write_text('original')
            result = self.run_prepare(SOURCE, out, t / 'lock.json')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('patch', result.stderr)
            self.assertEqual((out / 'keep').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
