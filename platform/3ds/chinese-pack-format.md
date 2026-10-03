# Chinese increment format, version 1

All integers are little-endian. The 56-byte header contains:

| Offset | Type | Value |
|---|---|---|
| 0 | 8 bytes | `Z3CNPK1` followed by NUL |
| 8 | uint32 | version: 1 |
| 12 | uint32 | message count: 397 |
| 16 | uint32 | CJK count: 1118 |
| 20 | uint32 | standard character count: 111 |
| 24 | uint32 | dialogue flags: 7 |
| 28 | six uint32 | section byte lengths |
| 52 | uint32 | CRC32 of all bytes after the header |

Sections follow immediately, without padding:

1. Dictionary packed table (empty for this version).
2. Packed table of 397 encoded Chinese messages, without the runtime terminator.
3. Sixteen punctuation glyphs: top 8x8 tile, bottom 8x8 tile, 32 bytes each.
4. Sixteen punctuation widths (1–8).
5. 1118 CJK glyphs: TL, TR, BL, BR 8x8 tiles, 64 bytes each.
6. 1118 CJK widths (1–13).

Tiles use the SNES 2BPP layout: each row has low/high bitplane bytes, most
significant bit at the left. Colors retain sxunix's blue outline and white body.
Glyphs are aligned to the left of their ink bounds so the fixed advance does
not clip them. Glyphs wider than the advance limit are fitted horizontally
with nearest-neighbor sampling; CJK advances remain at most 13 pixels.
Punctuation maps to character IDs 95–110. CJK IDs begin at 111; byte prefixes
0x6F–0x73 plus a second byte encode the CJK offset.

Packed tables use the engine's offset-table/body/count-trailer format. A zero
byte table contains no entries; a nonempty table has a uint16 trailer for
count minus one, with bit 13 selecting uint32 offsets instead of uint16.
The first offset is implicitly zero and the final offset is the body length.

At runtime, reuse the user's extracted 4096-byte US tile region and first
95 US widths. Replace punctuation tiles and append CJK tiles/widths. This
increment contains no US font, US dialogue, ROM or full game asset package.

Translation and font input come from the pinned sxunix dependency. The Ark
Pixel font is licensed under SIL OFL 1.1; ship `tables/FONT_LICENSE` with it.

## Text layout

The build shifts the row break in message 109 and adds a second row in message
165. Both source lines exceed the 168-pixel text row. All words are retained;
the pinned vendor checkout stays unchanged. An independent test checks every
pure Chinese/punctuation row against the generated advance widths.
