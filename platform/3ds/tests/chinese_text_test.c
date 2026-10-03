#include <stdio.h>
#include <stdlib.h>
static uint8_t font_data[4096 + 71552], widths[1229],
    font_pack[4096 + 71552 + 1229 + 6];
static void put16(uint8_t *p, unsigned x) {
  p[0] = x;
  p[1] = x >> 8;
}
static void init(void) {
  memset(g_ram, 0, sizeof(g_ram));
  memset(font_data, 255, sizeof(font_data));
  memset(widths, 13, sizeof(widths));
  memset(widths, 8, 111);
  font_pack[0] = sizeof(font_data) & 255;
  font_pack[1] = (sizeof(font_data) >> 8) & 255;
  font_pack[2] = sizeof(font_data) >> 16;
  font_pack[3] = 0;
  memcpy(font_pack + 4, font_data, sizeof(font_data));
  memcpy(font_pack + 4 + sizeof(font_data), widths, sizeof(widths));
  put16(font_pack + sizeof(font_pack) - 2, 8193);
  g_zenv.dialogue_font_blk = (MemBlk){font_pack, sizeof(font_pack)};
  g_zenv.dialogue_flags = 7;
  for (unsigned c = 0x74; c <= 0x7e; c++)
    assert(TEXTCMD_CMD(Text_DecodeCmd(c, NULL)) == kTextCmd_EndMessage);
  g_zenv.dialogue_flags = 1;
  assert(TEXTCMD_PARAM(Text_DecodeCmd(0x74, NULL)) == 0x74);
  g_zenv.dialogue_flags = 7;
}
static void expect_pixels(unsigned start, unsigned width) {
  uint8 expected[4096] = {0};
  for (unsigned row = 0; row < 16; row++)
    for (unsigned col = start; col < start + width; col++) {
      unsigned origin = (row >= 8 ? 0x150 : 0) + col * 2;
      unsigned byte = (origin & 0xff0) + (row % 8) * 2, bit = 0x80 >> (col % 8);
      expected[byte] |= bit;
      expected[byte + 1] |= bit;
    }
  assert(!memcmp(messaging_buf, expected, sizeof(expected)));
}
int main(int argc, char **argv) {
  init();
  const unsigned chars[] = {111, 366, 367, 1228};
  for (unsigned i = 0; i < 4; i++) {
    unsigned c = chars[i] - 111;
    uint8 tail = c & 255;
    uint32 cmd = Text_DecodeCmd(0x6f + c / 256, &tail);
    assert(TEXTCMD_PARAM(cmd) == chars[i]);
    assert(TEXTCMD_MULTIBYTE(cmd));
  }
  uint8 tail = 0x88;
  assert(TEXTCMD_PARAM(Text_DecodeCmd(0x6f, &tail)) == 247);
  g_zenv.dialogue_flags = 0;
  assert(TEXTCMD_PARAM(Text_DecodeCmd(10, NULL)) == 10);
  g_zenv.dialogue_flags = 7;
  for (unsigned i = 0; i < 2; i++) {
    init();
    VWF_RenderSingle(i ? 1228 : 111);
    assert(vwf_arr[vwf_var1] == 13);
    expect_pixels(0, 13);
  }
  init();
  vwf_arr[0] = 7;
  VWF_RenderSingle(111);
  expect_pixels(7, 13);
  init();
  vwf_arr[0] = 160;
  VWF_RenderSingle(111);
  assert(vwf_var1 == 0);
  assert(vwf_arr[0] == 160);
  init();
  VWF_RenderSingle(1229);
  VWF_RenderSingle(-1);
  assert(vwf_var1 == 0);
  init();
  font_pack[4 + sizeof(font_data) + 111] = 0;
  VWF_RenderSingle(111);
  assert(vwf_var1 == 0);
  init();
  font_pack[4 + sizeof(font_data) + 111] = 14;
  VWF_RenderSingle(111);
  assert(vwf_var1 == 0);
  init();
  g_zenv.dialogue_font_blk.size = 2;
  VWF_RenderSingle(111);
  assert(vwf_var1 == 0);
  /* One-entry message table inside a dictionary+message language container. */
  uint8 truncated[] = {0, 0, 0x6f, 0, 0, 1, 0};
  g_zenv.dialogue_blk = (MemBlk){truncated, sizeof(truncated)};
  dialogue_message_index = 0;
  Text_LoadCharacterBuffer();
  assert(messaging_text_buffer[0] == 0x7f);
  uint8 message[] = {0x6f, 0x88, 0x73, 0x5d, 0x85, 0x87, 0x20};
  uint8 container[64] = {0};
  put16(container, 0);
  memcpy(container + 2, message, sizeof(message));
  put16(container + 2 + sizeof(message), 0);
  put16(container + 4 + sizeof(message), 1);
  static uint8 sram[0x2000];
  g_zenv.sram = sram;
  srm_var1 = 2;
  memset(sram, 0, sizeof(sram));
  srm_var1 = 2;
  dialogue_number[0] = 0x42;
  g_zenv.dialogue_blk = (MemBlk){container, 6 + sizeof(message)};
  Text_LoadCharacterBuffer();
  assert(!memcmp(messaging_text_buffer, message, 4));
  for (int i = 4; i < 10; i++) assert(messaging_text_buffer[i] == 0);
  assert(messaging_text_buffer[10] == 0x36);
  assert(messaging_text_buffer[11] == 0x7f);
  uint8 invalid_tail = 0x4f;
  assert(TEXTCMD_CMD(Text_DecodeCmd(0x87, &invalid_tail)) ==
         kTextCmd_EndMessage);
  assert(TEXTCMD_CMD(Text_DecodeCmd(0x6f, NULL)) == kTextCmd_EndMessage);
  uint8 invalid_cjk = 255;
  assert(TEXTCMD_CMD(Text_DecodeCmd(0x73, &invalid_cjk)) ==
         kTextCmd_EndMessage);
  uint8 *long_text = calloc(1, 4004);
  assert(long_text);
  memset(long_text + 2, 10, 4000);
  put16(long_text + 4002, 1);
  init();
  g_zenv.dialogue_blk = (MemBlk){long_text, 4004};
  memset(g_ram + 0x11fc0, 0xa5, 32);
  Text_LoadCharacterBuffer();
  assert(memchr(messaging_text_buffer, 0x7f, 0xdc0));
  for (unsigned i = 0; i < 32; i++) assert(g_ram[0x11fc0 + i] == 0xa5);
  free(long_text);
  assert(argc == 2);
  FILE *file = fopen(argv[1], "rb");
  assert(file);
  assert(!fseek(file, 0, SEEK_END));
  long pack_size = ftell(file);
  rewind(file);
  uint8_t *pack = malloc((size_t)pack_size);
  assert(pack);
  assert(fread(pack, 1, (size_t)pack_size, file) == (size_t)pack_size);
  fclose(file);
  unsigned text_size = pack[32] | (unsigned)pack[33] << 8 |
                       (unsigned)pack[34] << 16 | (unsigned)pack[35] << 24;
  assert(text_size < 65536);
  uint8_t *language = malloc(text_size + 4);
  assert(language);
  put16(language, 0);
  memcpy(language + 2, pack + 56, text_size);
  put16(language + 2 + text_size, 1);
  init();
  g_zenv.sram = sram;
  memset(sram, 0, sizeof(sram));
  srm_var1 = 2;
  g_zenv.dialogue_blk = (MemBlk){language, text_size + 4};
  for (unsigned i = 0; i < 397; i++) {
    dialogue_message_index = i;
    memset(g_ram + 0x11fc0, 0xa5, 32);
    Text_LoadCharacterBuffer();
    assert(memchr(messaging_text_buffer, 0x7f, 0xdc0));
    for (unsigned j = 0; j < 32; j++) assert(g_ram[0x11fc0 + j] == 0xa5);
  }
  free(language);
  free(pack);
  puts("Chinese engine decode, substitutions, glyph pixels and bounds: PASS");
  return 0;
}
