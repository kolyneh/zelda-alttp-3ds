#include "chinese_assets.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t *read_file(const char *path, size_t *size) {
  FILE *f = fopen(path, "rb");
  assert(f);
  assert(!fseek(f, 0, SEEK_END));
  long n = ftell(f);
  assert(n >= 0);
  rewind(f);
  uint8_t *p = malloc((size_t)n);
  assert(p);
  assert(fread(p, 1, (size_t)n, f) == (size_t)n);
  fclose(f);
  *size = (size_t)n;
  return p;
}
int main(int argc, char **argv) {
  assert(argc == 3);
  size_t na, np;
  uint8_t *a = read_file(argv[1], &na), *p = read_file(argv[2], &np);
  uint8_t *out = NULL;
  size_t size = 0;
  char error[100];
  assert(ChineseAssets_Apply(a, na, p, np, &out, &size, error, sizeof(error)));
  assert(ChineseAssets_IsCurrent(out, size, p, np));
  free(out);
  unsigned seed = 0x12345678;
  for (unsigned i = 0; i < 3000; i++) {
    seed = seed * 1664525u + 1013904223u;
    size_t at = seed % np;
    uint8_t old = p[at];
    p[at] ^= (uint8_t)(1u << (seed % 8));
    bool ok =
        ChineseAssets_Apply(a, na, p, np, &out, &size, error, sizeof(error));
    assert(!ok && !out && !size);
    p[at] = old;
    size_t cut = seed % na;
    assert(
        !ChineseAssets_Apply(a, cut, p, np, &out, &size, error, sizeof(error)));
    assert(!out && !size);
  }
  free(a);
  free(p);
  puts("Chinese assets ASan/UBSan corrupted-input checks: PASS");
  return 0;
}
