import importlib.util
from io import BytesIO
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/3ds/fetch_build_inputs.py'

class FetchTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.is_file(), 'Pinned build-input preparation is missing')
        spec=importlib.util.spec_from_file_location('fetch_inputs',SCRIPT)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_digest_verified_before_atomic_promotion_and_cache_is_reused(self):
        module=self.module();data=b'pinned source';entry={'file':'source.tar.gz','url':'https://example.com/source','sha256':hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as t:
            with patch.object(module,'open_url',return_value=BytesIO(data)) as request:
                result=module.fetch(entry,Path(t));self.assertEqual(result.read_bytes(),data)
                module.fetch(entry,Path(t));self.assertEqual(request.call_count,1)
    def test_corrupt_download_does_not_replace_existing_file(self):
        module=self.module();entry={'file':'source.tar.gz','url':'https://example.com/source','sha256':hashlib.sha256(b'valid').hexdigest()}
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/entry['file'];dest.write_bytes(b'previous invalid cache')
            with patch.object(module,'open_url',return_value=BytesIO(b'corrupt')):
                with self.assertRaises(ValueError):module.fetch(entry,Path(t))
            self.assertEqual(dest.read_bytes(),b'previous invalid cache');self.assertFalse(Path(str(dest)+'.tmp').exists())
    def test_input_names_cannot_escape_download_directory(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):module.fetch({'file':'../escape','url':'https://example.com','sha256':'0'*64},Path(t))
