#ifndef ZELDA3_CHINESE_ASSETS_H
#define ZELDA3_CHINESE_ASSETS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
bool ChineseAssets_Apply(const uint8_t *assets, size_t assets_size,
                         const uint8_t *pack, size_t pack_size, uint8_t **out,
                         size_t *out_size, char *error, size_t error_size);
bool ChineseAssets_IsCurrent(const uint8_t *assets, size_t assets_size,
                             const uint8_t *pack, size_t pack_size);
#endif
