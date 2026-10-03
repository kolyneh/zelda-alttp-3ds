#!/usr/bin/env python3
"""Build a ROM-free Chinese dialogue/font increment from pinned sxunix."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import runpy
import struct
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
MAGIC = b'Z3CNPK1\0'
FONT_PATH = ROOT / 'platform/3ds/fonts/fusion-pixel-12px-monospaced-zh_hans.otf.woff'
FONT_SHA256 = '478f35c9be4bd2f527c6b35d789a6fcbb7f85f7dfa4f5a54d61ff0f10bdce37e'


def validate_font(path, characters):
    """Reject unmapped characters before Pillow substitutes .notdef boxes."""
    from fontTools.ttLib import TTFont
    with TTFont(path) as font:
        cmap = font.getBestCmap() or {}
        missing = [char for char in characters
                   if ord(char) not in cmap or font.getGlyphID(cmap[ord(char)]) == 0]
    if missing:
        raise ValueError('Chinese font is missing glyphs: ' + ''.join(missing))

# Keep the pinned translation intact while fitting two authored rows to 168 px.
LAYOUT_FIXES = {
    109: ('[2]现在可以打开[3]普通钥匙打不开的门和宝箱了！',
          '[2]现在可以打开普通钥匙[3]打不开的门和宝箱了！'),
    165: ('呼噜噜……呼噜噜……（打着响亮的鼾声）',
          '呼噜噜……呼噜噜……[2]（打着响亮的鼾声）'),
}


def reflow_dialogue(lines):
    lines = list(lines)
    for number, (before, after) in LAYOUT_FIXES.items():
        if before not in lines[number - 1]:
            raise ValueError(f'Pinned dialogue {number} changed; review its line layout')
        lines[number - 1] = lines[number - 1].replace(before, after, 1)
    return lines



def load_dialogue(engine):
    engine = Path(engine).resolve()
    saved_path, saved_bytecode = sys.path[:], sys.dont_write_bytecode
    try:
        sys.path.insert(0, str(engine / 'assets'))
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('sxunix_text', engine / 'assets/text_compression.py')
        codec = importlib.util.module_from_spec(spec); spec.loader.exec_module(codec)
    finally:
        sys.path[:], sys.dont_write_bytecode = saved_path, saved_bytecode
    path = engine / 'tables/dialogue_cn.txt'
    if not path.is_file():
        path = engine / 'assets/dialogue_cn.txt'
    lines = []
    for index, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        number, text = line.split(':', 1)
        if int(number) != index:
            raise ValueError('Chinese dialogue IDs must be consecutive')
        lines.append(text[1:] if text.startswith(' ') else text)
    info = codec.kLanguages['cn']
    if len(lines) != 397 or len(info.alphabet) != 111 or len(info.cjk_chars) != 1118:
        raise ValueError('Chinese resource counts do not match the pinned format')
    return codec, reflow_dialogue(lines)


def pack_arrays(parts):
    if not parts:
        return b''
    offsets, offset = [], 0
    for part in parts[:-1]:
        offset += len(part); offsets.append(offset)
    wide = offset >= 65536 or len(parts) > 8192
    return (b''.join(struct.pack('<I' if wide else '<H', value) for value in offsets)
            + b''.join(parts) + struct.pack('<H', len(parts) - 1 + (8192 if wide else 0)))


def encode_tile(image, x, y):
    data = bytearray()
    for row in range(8):
        low = high = 0
        for col in range(8):
            value = image.getpixel((x + col, y + row))
            if value not in range(4):
                raise ValueError('Font contains a non-2BPP palette entry')
            low |= (value & 1) << (7 - col)
            high |= ((value >> 1) & 1) << (7 - col)
        data.extend((low, high))
    return bytes(data)


def fit_glyph(image, x, y, limit):
    """Keep the entire glyph inside its rendered advance, including outline."""
    from PIL import Image
    cell = image.crop((x, y, x + 16, y + 16))
    box = cell.getbbox()
    if box is None:
        raise ValueError('Chinese font has an empty glyph')
    glyph = cell.crop((box[0], 0, box[2], 16))
    if glyph.width > limit:
        glyph = glyph.resize((limit, 16), Image.Resampling.NEAREST)
    fitted = Image.new('P', (16, 16), 0)
    fitted.paste(glyph, (0, 0))
    return fitted, min(glyph.width + 1, limit)


def build_pack(engine):
    engine = Path(engine).resolve()
    codec, lines = load_dialogue(engine)
    messages = [bytes(data) for data in codec.compress_strings(lines, 'cn')]
    saved_path, saved_bytecode = sys.path[:], sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        font = runpy.run_path(str(engine / 'tools/generate_font_cn.py'), run_name='sxunix_cn_font')
    finally:
        sys.path[:], sys.dont_write_bytecode = saved_path, saved_bytecode
    if font['CJK_CHARS'] != codec.kLanguages['cn'].cjk_chars:
        raise ValueError('Font and dialogue CJK character orders differ')
    if hashlib.sha256(FONT_PATH.read_bytes()).hexdigest() != FONT_SHA256:
        raise ValueError('Chinese font SHA-256 does not match the pinned input')
    validate_font(FONT_PATH, font['CN_PUNCT'] + font['CJK_CHARS'])
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='zelda3-cn-font-') as directory:
        from fontTools.ttLib import TTFont
        otf = Path(directory) / 'font.otf'
        with TTFont(FONT_PATH, recalcTimestamp=False) as source:
            source.flavor = None
            source.save(otf)
        # runpy functions retain their own globals; select the validated font
        # explicitly so the vendor's subset/system fallback cannot be used.
        font['generate_font_cn'].__globals__['FONT_PATH_PIXEL'] = str(otf)
        png = Path(directory) / 'font_cn.png'
        font['generate_font_cn'](png)
        with Image.open(png) as image:
            if image.mode != 'P' or image.size != (512, 576):
                raise ValueError('Unexpected Chinese font image layout')
            punctuation = bytearray(); punct_width = bytearray()
            cjk = bytearray(); cjk_width = bytearray()
            for index in range(1134):
                x, y = (index % 32) * 16, (index // 32) * 16
                if index < 16:
                    glyph, width = fit_glyph(image, x, y, 8)
                    punctuation.extend(encode_tile(glyph, 0, 0))
                    punctuation.extend(encode_tile(glyph, 0, 8))
                    punct_width.append(width)
                else:
                    glyph, width = fit_glyph(image, x, y, 13)
                    cjk.extend(encode_tile(glyph, 0, 0))
                    cjk.extend(encode_tile(glyph, 8, 0))
                    cjk.extend(encode_tile(glyph, 0, 8))
                    cjk.extend(encode_tile(glyph, 8, 8))
                    cjk_width.append(width)
    parts = [pack_arrays([]), pack_arrays(messages), bytes(punctuation),
             bytes(punct_width), bytes(cjk), bytes(cjk_width)]
    payload = b''.join(parts)
    header = MAGIC + struct.pack('<12I', 1, 397, 1118, 111, 7,
                                *(len(part) for part in parts), zlib.crc32(payload))
    return header + payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, default=ROOT / 'vendor/zelda3')
    parser.add_argument('--output', type=Path, default=ROOT / 'build-3ds/chinese/zelda3_cn.pack')
    args = parser.parse_args()
    try:
        data = build_pack(args.engine)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print('Chinese pack: ' + str(exc), file=sys.stderr)
        return 1
    print(f'Generated {args.output}: {len(data)} bytes, 397 Chinese messages, no ROM required')
    return 0


if __name__ == '__main__':
    sys.exit(main())
