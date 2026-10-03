#include "chinese_assets.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  const uint8_t *p;
  size_t n;
} View;
typedef struct {
  uint8_t *p;
  size_t n;
} Blob;
static const uint8_t signature[48] = {
    90, 101, 108, 100, 97,  51,  95,  118, 48,  32,  32,  32,
    32, 32,  10,  0,   27,  174, 233, 45,  74,  174, 252, 50,
    49, 27,  153, 197, 27,  43,  216, 197, 132, 101, 173, 169,
    36, 108, 15,  155, 176, 169, 57,  131, 174, 101, 51,  207};
static uint32_t rd32(const uint8_t *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 |
         (uint32_t)p[3] << 24;
}
static unsigned rd16(const uint8_t *p) { return p[0] | (unsigned)p[1] << 8; }
static void wr32(uint8_t *p, uint32_t v) {
  for (unsigned i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (i * 8));
}
static uint32_t crc32(View v) {
  uint32_t crc = UINT32_MAX;
  for (size_t i = 0; i < v.n; i++) {
    crc ^= v.p[i];
    for (int j = 0; j < 8; j++)
      crc = (crc >> 1) ^ ((0u - (crc & 1)) & 0xedb88320u);
  }
  return ~crc;
}
/* Array trailers store count-1 and the 32-bit-offset flag. Offsets must be
 * monotone. */
static bool unpack(View v, View **out, size_t *count) {
  *out = NULL;
  *count = 0;
  if (!v.n) return true;
  if (v.n < 2) return false;
  unsigned mark = rd16(v.p + v.n - 2);
  if (mark & 0xc000) return false;
  size_t n = (mark & 8191) + 1, width = (mark & 8192) ? 4 : 2,
         head = (n - 1) * width;
  if (head > v.n - 2) return false;
  size_t body = v.n - 2 - head, prev = 0;
  View *a = calloc(n + 1, sizeof(*a));
  if (!a) return false;
  for (size_t i = 0; i < n; i++) {
    size_t next = i + 1 == n ? body
                             : (width == 4 ? rd32(v.p + i * width)
                                           : rd16(v.p + i * width));
    if (next < prev || next > body) {
      free(a);
      return false;
    }
    a[i] = (View){v.p + head + prev, next - prev};
    prev = next;
  }
  *out = a;
  *count = n;
  return true;
}
static bool pack_table(const View *a, size_t n, Blob *out) {
  if (!n || n > 8192) return false;
  size_t body = 0, last = 0;
  for (size_t i = 0; i < n; i++) {
    last = body;
    if (a[i].n > UINT32_MAX - body) return false;
    body += a[i].n;
  }
  size_t width = last >= 65536 ? 4 : 2, head = (n - 1) * width;
  if (body > UINT32_MAX - head - 2) return false;
  out->n = head + body + 2;
  out->p = malloc(out->n);
  if (!out->p) return false;
  size_t pos = 0;
  for (size_t i = 0; i < n; i++) {
    if (a[i].n) memcpy(out->p + head + pos, a[i].p, a[i].n);
    pos += a[i].n;
    if (i + 1 < n) {
      if (width == 4)
        wr32(out->p + i * width, (uint32_t)pos);
      else {
        out->p[i * 2] = (uint8_t)pos;
        out->p[i * 2 + 1] = (uint8_t)(pos >> 8);
      }
    }
  }
  unsigned mark = (unsigned)(n - 1) | (width == 4 ? 8192 : 0);
  out->p[out->n - 2] = (uint8_t)mark;
  out->p[out->n - 1] = (uint8_t)(mark >> 8);
  return true;
}
static View view(Blob b) { return (View){b.p, b.n}; }
static bool same(View a, View b) {
  return a.n == b.n && (!a.n || memcmp(a.p, b.p, a.n) == 0);
}
static bool name_is(View a, const char *s) {
  size_t n = strlen(s);
  return a.n == n && !memcmp(a.p, s, n);
}

static bool read_pack(View input, View parts[6]) {
  if (input.n < 56 || memcmp(input.p, "Z3CNPK1\0", 8) ||
      rd32(input.p + 8) != 1 || rd32(input.p + 12) != 397 ||
      rd32(input.p + 16) != 1118 || rd32(input.p + 20) != 111 ||
      rd32(input.p + 24) != 7)
    return false;
  size_t pos = 56;
  for (int i = 0; i < 6; i++) {
    size_t n = rd32(input.p + 28 + i * 4);
    if (n > input.n - pos) return false;
    parts[i] = (View){input.p + pos, n};
    pos += n;
  }
  if (pos != input.n ||
      crc32((View){input.p + 56, input.n - 56}) != rd32(input.p + 52) ||
      parts[0].n || parts[2].n != 512 || parts[3].n != 16 ||
      parts[4].n != 71552 || parts[5].n != 1118)
    return false;
  for (size_t i = 0; i < 16; i++)
    if (!parts[3].p[i] || parts[3].p[i] > 8) return false;
  for (size_t i = 0; i < 1118; i++)
    if (!parts[5].p[i] || parts[5].p[i] > 13) return false;
  View *messages = NULL;
  size_t count = 0;
  bool ok = unpack(parts[1], &messages, &count) && count == 397;
  free(messages);
  return ok;
}

bool ChineseAssets_Apply(const uint8_t *assets, size_t assets_size,
                         const uint8_t *pack, size_t pack_size, uint8_t **out,
                         size_t *out_size, char *error, size_t error_size) {
  if (out) *out = NULL;
  if (out_size) *out_size = 0;
  if (error && error_size) error[0] = 0;
  const char *reason = "Invalid Chinese pack or assets";
  View slots[165], parts[6], *dialogues = NULL, *fonts = NULL, *mappings = NULL,
                             *font = NULL;
  View *names = NULL, *configs = NULL;
  size_t dialogue_count = 0, font_count = 0, map_count = 0, base_font_count = 0,
         header = 0;
  // Glyph pixels, widths, language font/dialogue/map entry, then three asset
  // tables.
  Blob owned[8] = {{0}};
  uint8_t *result = NULL;
  bool ok = false;
  if (!out || !out_size || !assets || !pack ||
      !read_pack((View){pack, pack_size}, parts))
    goto done;
  if (assets_size < 748 || memcmp(assets, signature, 48) ||
      rd32(assets + 80) != 165)
    goto done;
  size_t names_size = rd32(assets + 84);
  if (names_size > assets_size - 748) goto done;
  header = 748 + names_size;
  size_t pos = header;
  for (size_t i = 0; i < 165; i++) {
    if (pos > assets_size || assets_size - pos < ((-pos) & 3)) goto done;
    pos = (pos + 3) & ~(size_t)3;
    size_t n = rd32(assets + 88 + i * 4);
    if (n > assets_size - pos) goto done;
    slots[i] = (View){assets + pos, n};
    pos += n;
  }
  if (pos != assets_size || !unpack(slots[94], &dialogues, &dialogue_count) ||
      !unpack(slots[95], &fonts, &font_count) ||
      !unpack(slots[96], &mappings, &map_count) || !dialogue_count ||
      !font_count || !map_count || dialogue_count > 255 || font_count > 255 ||
      map_count > 255)
    goto done;
  names = calloc(map_count, sizeof(*names));
  configs = calloc(map_count, sizeof(*configs));
  if (!names || !configs) goto done;
  int us = -1, cn = -1;
  for (size_t i = 0; i < map_count; i++) {
    View *entry = NULL;
    size_t ne = 0;
    if (!unpack(mappings[i], &entry, &ne)) goto done;
    if (ne != 2 || !entry[0].n || entry[0].n > 32 || entry[1].n != 3 ||
        entry[1].p[0] >= dialogue_count || entry[1].p[1] >= font_count) {
      free(entry);
      goto done;
    }
    names[i] = entry[0];
    configs[i] = entry[1];
    free(entry);
    for (size_t j = 0; j < i; j++)
      if (same(names[i], names[j])) goto done;
    if (name_is(names[i], "us")) us = (int)i;
    if (name_is(names[i], "cn")) cn = (int)i;
  }
  if (us < 0 || !unpack(fonts[configs[us].p[1]], &font, &base_font_count) ||
      base_font_count != 2 || font[0].n < 4096 || font[1].n < 95) {
    reason = "Missing usable US font";
    goto done;
  }
  owned[0].n = 4096 + 71552;
  owned[0].p = malloc(owned[0].n);
  owned[1].n = 1229;
  owned[1].p = malloc(1229);
  if (!owned[0].p || !owned[1].p) goto done;
  memcpy(owned[0].p, font[0].p, 4096);
  for (size_t i = 0; i < 16; i++) {
    size_t c = 95 + i, tile = (c & 0x70) * 2 + (c & 15);
    memcpy(owned[0].p + tile * 16, parts[2].p + i * 32, 16);
    memcpy(owned[0].p + (tile + 16) * 16, parts[2].p + i * 32 + 16, 16);
  }
  memcpy(owned[0].p + 4096, parts[4].p, 71552);
  memcpy(owned[1].p, font[1].p, 95);
  memcpy(owned[1].p + 95, parts[3].p, 16);
  memcpy(owned[1].p + 111, parts[5].p, 1118);
  View fv[2] = {view(owned[0]), view(owned[1])}, dv[2] = {parts[0], parts[1]};
  if (!pack_table(fv, 2, &owned[2]) || !pack_table(dv, 2, &owned[3])) goto done;
  size_t dialogue_index = dialogue_count, font_index = font_count,
         map_index = map_count;
  // Reuse exclusive CN slots. Shared slots belong to another language as well.
  if (cn >= 0) {
    map_index = (size_t)cn;
    dialogue_index = configs[cn].p[0];
    font_index = configs[cn].p[1];
    for (size_t i = 0; i < map_count; i++)
      if ((int)i != cn) {
        if (configs[i].p[0] == dialogue_index) dialogue_index = dialogue_count;
        if (configs[i].p[1] == font_index) font_index = font_count;
      }
  }
  if (dialogue_index == dialogue_count) {
    if (dialogue_count == 255) goto done;
    dialogue_count++;
  }
  if (font_index == font_count) {
    if (font_count == 255) goto done;
    font_count++;
  }
  if (map_index == map_count) {
    if (map_count == 255) goto done;
    map_count++;
  }
  dialogues[dialogue_index] = view(owned[3]);
  fonts[font_index] = view(owned[2]);
  uint8_t conf[3] = {(uint8_t)dialogue_index, (uint8_t)font_index, 7};
  View mv[2] = {{(const uint8_t *)"cn", 2}, {conf, 3}};
  if (!pack_table(mv, 2, &owned[4])) goto done;
  mappings[map_index] = view(owned[4]);
  if (!pack_table(dialogues, dialogue_count, &owned[5]) ||
      !pack_table(fonts, font_count, &owned[6]) ||
      !pack_table(mappings, map_count, &owned[7]))
    goto done;
  for (int i = 0; i < 3; i++) slots[94 + i] = view(owned[5 + i]);
  size_t total = header;
  for (size_t i = 0; i < 165; i++) {
    size_t pad = (-total) & 3;
    if (pad > UINT32_MAX - total || slots[i].n > UINT32_MAX - total - pad)
      goto done;
    total += pad + slots[i].n;
  }
  result = calloc(1, total);
  if (!result) goto done;
  memcpy(result, assets, header);
  pos = header;
  for (size_t i = 0; i < 165; i++) {
    wr32(result + 88 + i * 4, (uint32_t)slots[i].n);
    pos = (pos + 3) & ~(size_t)3;
    if (slots[i].n) memcpy(result + pos, slots[i].p, slots[i].n);
    pos += slots[i].n;
  }
  *out = result;
  *out_size = total;
  result = NULL;
  ok = true;
done:
  if (!ok && error && error_size) snprintf(error, error_size, "%s", reason);
  free(result);
  free(dialogues);
  free(fonts);
  free(mappings);
  free(font);
  free(names);
  free(configs);
  for (int i = 0; i < 8; i++) free(owned[i].p);
  return ok;
}
bool ChineseAssets_IsCurrent(const uint8_t *assets, size_t assets_size,
                             const uint8_t *pack, size_t pack_size) {
  uint8_t *out = NULL;
  size_t size = 0;
  if (!ChineseAssets_Apply(assets, assets_size, pack, pack_size, &out, &size,
                           NULL, 0))
    return false;
  bool same_assets = size == assets_size && !memcmp(out, assets, size);
  free(out);
  return same_assets;
}
