import importlib.util
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'tools/3ds/build_cn_pack.py'
ENGINE = ROOT / 'vendor/zelda3'


def unpack_table(data):
    if not data:
        return []
    marker, = struct.unpack_from('<H', data, len(data) - 2)
    width = 4 if marker & 8192 else 2
    count = (marker & 8191) + 1
    begin = (count - 1) * width
    offsets = [0] + [int.from_bytes(data[i * width:(i + 1) * width], 'little')
                     for i in range(count - 1)] + [len(data) - 2 - begin]
    return [data[begin + offsets[i]:begin + offsets[i + 1]] for i in range(count)]


def decode_message(data, info):
    # Independent decoder for the published CN encoding, not the builder.
    simple = {0x80: 'Scroll', 0x81: 'Waitkey', 0x82: '1', 0x83: '2', 0x84: '3', 0x85: 'Name'}
    extra = ['Choose', 'Choose2', 'Choose3', 'Selchg', 'Item', 'NextPic', 'Window 2', 'Position 0', 'Position 1']
    text = ''; i = 0
    while i < len(data):
        a = data[i]; i += 1
        if 0x6f <= a <= 0x73:
            text += info.cjk_chars[(a - 0x6f) * 256 + data[i]]; i += 1
        elif a < 111:
            text += info.alphabet[a]
        elif a == 0x87:
            b = data[i]; i += 1
            if b == 0x40:
                command = 'Sound 45'
            elif b >= 0x80:
                command = extra[b - 0x80]
            else:
                command = ['Wait', 'Color', 'Number', 'Speed'][b >> 4] + ' ' + str(b & 15)
            text += '[' + command + ']'
        else:
            text += '[' + simple[a] + ']'
    return text


def normalize(text):
    text = text.replace('[ScrollSpd 00]', '').replace('[Window 00]', '')
    return re.sub(r'\[([A-Za-z]+) (\d+)\]', lambda m: '[' + m[1] + ' ' + str(int(m[2])) + ']', text)


class ChinesePackTests(unittest.TestCase):
    def builder(self):
        self.assertTrue(SCRIPT.is_file(), 'Chinese pack builder is missing')
        spec = importlib.util.spec_from_file_location('build_cn_pack', SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_cli_generates_pack_without_any_rom(self):
        with tempfile.TemporaryDirectory() as t:
            output = Path(t) / 'cn.pack'
            result = subprocess.run([sys.executable, str(SCRIPT), '--engine', str(ENGINE), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = output.read_bytes()
            self.assertEqual(data[:8], b'Z3CNPK1\0')
            words = struct.unpack_from('<12I', data, 8)
            self.assertEqual(words[:5], (1, 397, 1118, 111, 7))
            self.assertEqual(len(data), 56 + sum(words[5:11]))
            self.assertEqual(zlib.crc32(data[56:]), words[11])
            parts = []; p = 56
            for length in words[5:11]:
                parts.append(data[p:p+length]); p += length
            self.assertEqual(parts[0], b'')
            self.assertEqual(len(unpack_table(parts[1])), 397)
            self.assertEqual(list(map(len, parts[2:])), [512, 16, 71552, 1118])
            self.assertTrue(all(1 <= x <= 8 for x in parts[3]))
            self.assertTrue(all(1 <= x <= 13 for x in parts[5]))

    def test_all_translations_roundtrip_and_commands_survive(self):
        builder = self.builder()
        codec, lines = builder.load_dialogue(ENGINE)
        encoded = codec.compress_strings(lines, 'cn')
        self.assertEqual(len(encoded), 397)
        for index, (text, data) in enumerate(zip(lines, encoded)):
            self.assertEqual(normalize(decode_message(data, codec.kLanguages['cn'])), normalize(text), index)
        self.assertEqual(bytes(codec.compress_strings(['[Name]，[2][Waitkey]'], 'cn')[0]),
                         bytes([0x85, 0x5f, 0x83, 0x81]))

    def test_all_escape_banks_and_dictionary_range_tail_bytes(self):
        codec, _ = self.builder().load_dialogue(ENGINE)
        info = codec.kLanguages['cn']
        for index, want in [(0, b'\x6f\x00'), (136, b'\x6f\x88'), (255, b'\x6f\xff'),
                            (256, b'\x70\x00'), (512, b'\x71\x00'), (768, b'\x72\x00'), (1117, b'\x73\x5d')]:
            encoded, = codec.compress_strings([info.cjk_chars[index]], 'cn')
            self.assertEqual(bytes(encoded), want)
            self.assertEqual(decode_message(encoded, info), info.cjk_chars[index])

    def test_reflow_preserves_words_and_fits_chinese_rows(self):
        builder = self.builder()
        codec, lines = builder.load_dialogue(ENGINE)
        original = [line.split(':', 1)[1].removeprefix(' ') for line in
                    (ENGINE / 'tables/dialogue_cn.txt').read_text(encoding='utf-8').splitlines()]
        for a, b in zip(original, lines):
            self.assertEqual(re.sub(r'\[[123]\]', '', a), re.sub(r'\[[123]\]', '', b))
        data = builder.build_pack(ENGINE); words = struct.unpack_from('<12I', data, 8)
        offset = 56 + sum(words[5:8]); punctuation = data[offset:offset+16]
        offset = 56 + sum(words[5:10]); cjk = data[offset:offset+1118]
        info = codec.kLanguages['cn']
        widths = {char: cjk[i] for i, char in enumerate(info.cjk_chars)}
        widths.update({char: punctuation[i-95] for i, char in enumerate(info.alphabet) if i >= 95})
        for number, line in enumerate(lines, 1):
            for row in re.split(r'\[(?:[123]|Scroll)\]', line):
                row = re.sub(r'\[[^]]*\]', '', row)
                if row and all(char in widths for char in row):
                    self.assertLessEqual(sum(widths[char] for char in row), 168, (number, row))

    def test_pack_is_deterministic_and_does_not_need_us_font(self):
        builder = self.builder()
        self.assertEqual(builder.build_pack(ENGINE), builder.build_pack(ENGINE))
        self.assertFalse((ENGINE / 'tables/font_us.png').exists())

    def test_glyph_pixels_fit_declared_rendering_width(self):
        data = self.builder().build_pack(ENGINE)
        words = struct.unpack_from('<12I', data, 8)
        begin = 56 + sum(words[5:9])
        tiles, widths = data[begin:begin + 71552], data[-1118:]
        for c in range(1118):
            for row in range(16):
                for col in range(widths[c], 16):
                    tile = (2 if row >= 8 else 0) + (1 if col >= 8 else 0)
                    pos = c * 64 + tile * 16 + (row % 8) * 2
                    self.assertFalse((tiles[pos] | tiles[pos + 1]) & (1 << (7 - col % 8)),
                                     f'CJK {c}: visible pixels would be clipped at column {col}')


if __name__ == '__main__':
    unittest.main()
