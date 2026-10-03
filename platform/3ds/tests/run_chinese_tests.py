#!/usr/bin/env python3
"""Exercise the production Chinese asset merger with independent synthetic assets."""
import ctypes
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from test_chinese_pack import unpack_table
spec = importlib.util.spec_from_file_location('cn_builder', ROOT / 'tools/3ds/build_cn_pack.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
pack_arrays = builder.pack_arrays
SIG = bytes([90,101,108,100,97,51,95,118,48,32,32,32,32,32,10,0,27,174,233,45,74,174,252,50,49,27,153,197,27,43,216,197,132,101,173,169,36,108,15,155,176,169,57,131,174,101,51,207])


def make_assets(slots=None):
    if slots is None:
        slots = [bytes([i]) * (i % 7 + 1) for i in range(165)]
        slots[94] = pack_arrays([pack_arrays([b'', pack_arrays([b'us dialogue'])])])
        slots[95] = pack_arrays([pack_arrays([bytes(range(256)) * 16, bytes(range(95))])])
        slots[96] = pack_arrays([pack_arrays([b'us', b'\0\0\0'])])
    names = b'synthetic\0'
    result = bytearray(SIG + bytes(32) + struct.pack('<II', 165, len(names)))
    result += struct.pack('<165I', *map(len, slots)) + names
    for slot in slots:
        result += bytes((-len(result)) % 4) + slot
    return bytes(result)


def get_slots(data):
    names, = struct.unpack_from('<I', data, 84)
    p = 748 + names; result = []
    for size in struct.unpack_from('<165I', data, 88):
        p = (p + 3) & ~3
        result.append(data[p:p+size]); p += size
    return result


class MergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        lib = Path(cls.temp.name) / 'cn.so'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        str(ROOT / 'platform/3ds/source/chinese_assets.c'), '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.ChineseAssets_Apply.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                                               ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.ChineseAssets_Apply.restype = ctypes.c_bool
        cls.lib.ChineseAssets_IsCurrent.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.ChineseAssets_IsCurrent.restype = ctypes.c_bool
        cls.free = ctypes.CDLL(None).free; cls.free.argtypes = [ctypes.c_void_p]
        cls.pack = builder.build_pack(ROOT / 'vendor/zelda3')
        cls.assets = make_assets()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def apply(self, data, pack=None, valid=True):
        pack = self.pack if pack is None else pack
        out = ctypes.c_void_p(123); size = ctypes.c_size_t(456); error = ctypes.create_string_buffer(256)
        ok = self.lib.ChineseAssets_Apply(data, len(data), pack, len(pack), ctypes.byref(out), ctypes.byref(size), error, 256)
        if valid:
            self.assertTrue(ok, error.value.decode()); result = ctypes.string_at(out, size.value); self.free(out)
            return result
        self.assertFalse(ok); self.assertIsNone(out.value); self.assertEqual(size.value, 0); self.assertTrue(error.value)

    def test_merge_retains_assets_and_builds_expected_font(self):
        out = self.apply(self.assets); old, slots = get_slots(self.assets), get_slots(out)
        for i in range(165):
            if i not in (94, 95, 96): self.assertEqual(slots[i], old[i], i)
        self.assertEqual(unpack_table(slots[94])[0], unpack_table(old[94])[0])
        font, widths = unpack_table(unpack_table(slots[95])[1])
        self.assertEqual(len(font), 4096 + 71552); self.assertEqual(len(widths), 1229)
        self.assertEqual(widths[:95], bytes(range(95)))
        entries = [unpack_table(x) for x in unpack_table(slots[96])]
        self.assertEqual(entries, [[b'us', b'\0\0\0'], [b'cn', b'\1\1\7']])
        self.assertTrue(self.lib.ChineseAssets_IsCurrent(out, len(out), self.pack, len(self.pack)))
        self.assertFalse(self.lib.ChineseAssets_IsCurrent(self.assets, len(self.assets), self.pack, len(self.pack)))
        self.assertEqual(out, self.apply(out))

    def test_keep_other_languages_and_update_existing_cn(self):
        slots = get_slots(self.apply(self.assets))
        dialogs, fonts, maps = map(unpack_table, slots[94:97])
        dialogs.append(b'other dialogue'); fonts.append(b'other font'); maps.append(pack_arrays([b'fr', b'\2\2\2']))
        dialogs[1] = b'outdated chinese'; fonts[1] = b'outdated font'
        slots[94:97] = map(pack_arrays, (dialogs, fonts, maps))
        out = get_slots(self.apply(make_assets(slots)))
        self.assertEqual(unpack_table(out[94])[2], b'other dialogue')
        self.assertEqual(unpack_table(out[95])[2], b'other font')
        self.assertEqual(len(unpack_table(out[96])), 3)

    def test_font_only_update_refreshes_existing_chinese_cache(self):
        current = self.apply(self.assets)
        slots = get_slots(current)
        fonts = unpack_table(slots[95])
        tiles, widths = unpack_table(fonts[1])
        old_tiles = bytearray(tiles)
        old_tiles[4096] ^= 1
        fonts[1] = pack_arrays([bytes(old_tiles), widths])
        slots[95] = pack_arrays(fonts)
        old = make_assets(slots)
        self.assertFalse(self.lib.ChineseAssets_IsCurrent(old, len(old), self.pack, len(self.pack)))
        self.assertEqual(self.apply(old), current)

    def test_cn_shared_slots_do_not_replace_us_resources(self):
        slots = get_slots(self.assets)
        slots[96] = pack_arrays([pack_arrays([b'us', b'\0\0\0']),
                                 pack_arrays([b'cn', b'\0\0\7'])])
        result = get_slots(self.apply(make_assets(slots)))
        self.assertEqual(unpack_table(result[94])[0], unpack_table(slots[94])[0])
        self.assertEqual(unpack_table(result[95])[0], unpack_table(slots[95])[0])
        self.assertEqual(unpack_table(unpack_table(result[96])[1]), [b'cn', b'\1\1\7'])
        self.assertEqual(len(unpack_table(result[96])), 2)

    def test_corrupt_pack_and_lengths(self):
        for cut in (0, 7, 55, 56, len(self.pack)-1): self.apply(self.assets, self.pack[:cut], False)
        for index in (0, 8, 12, 16, 20, 24, 28, 48, 52, 60, len(self.pack)-1):
            bad = bytearray(self.pack); bad[index] ^= 0xff; self.apply(self.assets, bytes(bad), False)
        bad = bytearray(self.pack); bad[56 + sum(struct.unpack_from('<6I', bad, 28)[:3])] = 0
        struct.pack_into('<I', bad, 52, zlib.crc32(bad[56:])); self.apply(self.assets, bytes(bad), False)

    def test_sanitized_parser_with_corrupted_input(self):
        directory = Path(self.temp.name)
        a, p, exe = directory / 'assets.dat', directory / 'cn.pack', directory / 'sanitized'
        a.write_bytes(self.assets); p.write_bytes(self.pack)
        subprocess.run(['cc', '-std=c11', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I', str(ROOT / 'platform/3ds/source'),
                        str(ROOT / 'platform/3ds/source/chinese_assets.c'),
                        str(ROOT / 'platform/3ds/tests/chinese_assets_test.c'), '-o', str(exe)], check=True)
        import os
        subprocess.run([str(exe), str(a), str(p)], check=True,
                       env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})

    def test_corrupt_assets_and_maps(self):
        for cut in (0, 47, 87, 747, len(self.assets)-1): self.apply(self.assets[:cut], valid=False)
        for index in (0, 80, 84, 88):
            bad = bytearray(self.assets); bad[index:index+4] = b'\xff'*4; self.apply(bytes(bad), valid=False)
        slots = get_slots(self.assets)
        for maps in ([pack_arrays([b'us', b'\xff\0\0'])],
                     [pack_arrays([b'us', b'\0\0\0']), pack_arrays([b'us', b'\0\0\0'])],
                     [pack_arrays([b'cn', b'\0\0\7']), pack_arrays([b'cn', b'\0\0\7'])]):
            slots[96] = pack_arrays(maps); self.apply(make_assets(slots), valid=False)
        slots = get_slots(self.assets); slots[95] = pack_arrays([pack_arrays([b'too short', b'widths'])])
        self.apply(make_assets(slots), valid=False)


if __name__ == '__main__':
    unittest.main()
