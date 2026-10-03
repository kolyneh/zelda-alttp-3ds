#ifndef ZELDA3_CHINESE_PROFILE_H
#define ZELDA3_CHINESE_PROFILE_H
#include <stdbool.h>
#include <stddef.h>
typedef enum {
  CN_PROFILE_ERROR = -1,
  CN_PROFILE_CURRENT = 0,
  CN_PROFILE_UPDATED = 1
} ChineseProfileResult;
/* Restore a stopped SD promotion before deciding whether extraction is
 * necessary. */
bool ChineseProfile_RecoverFile(const char *path, char *error,
                                size_t error_size);
ChineseProfileResult ChineseProfile_Ensure(const char *assets_path,
                                           const char *pack_path, char *error,
                                           size_t error_size);
/* Call after Ensure succeeds. A per-profile marker preserves later language
 * choices. */
bool ChineseProfile_SetDefaultLanguage(const char *ini_path, char *error,
                                       size_t error_size);
#endif
