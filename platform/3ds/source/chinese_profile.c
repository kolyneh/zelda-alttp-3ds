#include "chinese_profile.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

#include "chinese_assets.h"

static bool fail(char *error, size_t size, const char *reason,
                 const char *path) {
  if (error && size)
    snprintf(error, size, "%s: %s (errno=%d)", reason, path ? path : "", errno);
  return false;
}
static bool regular(const char *path) {
  struct stat st;
  return stat(path, &st) == 0 && S_ISREG(st.st_mode);
}
static bool suffix(char out[1024], const char *path, const char *tail,
                   char *error, size_t error_size) {
  if (!path || snprintf(out, 1024, "%s%s", path, tail) >= 1024)
    return fail(error, error_size, "Chinese migration path too long", path);
  return true;
}
static bool recover(const char *path, char *error, size_t error_size) {
  char backup[1024];
  if (!suffix(backup, path, ".cn.bak", error, error_size)) return false;
  if (!regular(path) && regular(backup) && rename(backup, path) != 0)
    return fail(error, error_size, "Chinese migration recovery failed", path);
  return true;
}
bool ChineseProfile_RecoverFile(const char *path, char *error,
                                size_t error_size) {
  if (error && error_size) error[0] = 0;
  return recover(path, error, error_size);
}
static bool read_file(const char *path, size_t limit, uint8_t **out,
                      size_t *size, char *error, size_t error_size) {
  *out = NULL;
  *size = 0;
  FILE *file = fopen(path, "rb");
  if (!file)
    return fail(error, error_size, "Chinese migration read failed", path);
  bool ok = fseek(file, 0, SEEK_END) == 0;
  long n = ok ? ftell(file) : -1;
  if (n < 0 || (unsigned long)n > limit || fseek(file, 0, SEEK_SET) != 0)
    ok = false;
  uint8_t *data = ok ? malloc((size_t)n + 1) : NULL;
  if (!data) ok = false;
  if (ok && fread(data, 1, (size_t)n, file) != (size_t)n) ok = false;
  if (fclose(file) != 0) ok = false;
  if (!ok) {
    free(data);
    return fail(error, error_size,
                "Chinese migration invalid file or read error", path);
  }
  data[n] = 0;
  *out = data;
  *size = (size_t)n;
  return true;
}
/* libctru SD rename cannot overwrite. Retain an old complete file until
 * promotion succeeds; a stopped promotion is restored by recover() on the next
 * launch. */
static bool replace(const char *path, const uint8_t *data, size_t size,
                    char *error, size_t error_size) {
  char temporary[1024], backup[1024];
  if (!suffix(temporary, path, ".cn.tmp", error, error_size) ||
      !suffix(backup, path, ".cn.bak", error, error_size))
    return false;
  FILE *file = fopen(temporary, "wb");
  if (!file)
    return fail(error, error_size, "Chinese migration temporary file failed",
                temporary);
  bool ok = fwrite(data, 1, size, file) == size;
  if (fclose(file) != 0) ok = false;
  if (!ok) {
    remove(temporary);
    return fail(error, error_size, "Chinese migration write failed", temporary);
  }
  uint8_t *check = NULL;
  size_t check_size = 0;
  ok = read_file(temporary, size, &check, &check_size, error, error_size) &&
       check_size == size && !memcmp(check, data, size);
  free(check);
  if (!ok) {
    remove(temporary);
    return fail(error, error_size, "Chinese migration verification failed",
                temporary);
  }
  bool had_original = regular(path);
  if (regular(backup) && remove(backup) != 0) {
    remove(temporary);
    return fail(error, error_size, "Chinese migration backup cleanup failed",
                backup);
  }
  if (had_original && rename(path, backup) != 0) {
    remove(temporary);
    return fail(error, error_size, "Chinese migration backup failed", path);
  }
  if (rename(temporary, path) != 0) {
    int saved_errno = errno;
    if (had_original) rename(backup, path);
    remove(temporary);
    errno = saved_errno;
    return fail(error, error_size, "Chinese migration promotion failed", path);
  }
  // Failure to remove this stale backup is harmless: the installed file is
  // complete.
  if (had_original) remove(backup);
  return true;
}
ChineseProfileResult ChineseProfile_Ensure(const char *assets_path,
                                           const char *pack_path, char *error,
                                           size_t error_size) {
  if (error && error_size) error[0] = 0;
  uint8_t *assets = NULL, *pack = NULL, *merged = NULL;
  size_t assets_size = 0, pack_size = 0, merged_size = 0;
  ChineseProfileResult result = CN_PROFILE_ERROR;
  if (!assets_path || !pack_path) {
    fail(error, error_size, "Missing Chinese migration path", "");
    return result;
  }
  if (!recover(assets_path, error, error_size) ||
      !read_file(assets_path, 16 * 1024 * 1024, &assets, &assets_size, error,
                 error_size) ||
      !read_file(pack_path, 1024 * 1024, &pack, &pack_size, error, error_size))
    goto done;
  if (!ChineseAssets_Apply(assets, assets_size, pack, pack_size, &merged,
                           &merged_size, error, error_size))
    goto done;
  if (merged_size == assets_size && !memcmp(merged, assets, assets_size)) {
    result = CN_PROFILE_CURRENT;
  } else if (replace(assets_path, merged, merged_size, error, error_size)) {
    result = CN_PROFILE_UPDATED;
  }
  if (result != CN_PROFILE_ERROR) {
    char backup[1024];
    if (suffix(backup, assets_path, ".cn.bak", NULL, 0)) remove(backup);
  }
done:
  free(assets);
  free(pack);
  free(merged);
  return result;
}
static char *trim(char *text) {
  while (*text == ' ' || *text == '\t' || *text == '\r' || *text == '\n')
    text++;
  size_t n = strlen(text);
  while (n && (text[n - 1] == ' ' || text[n - 1] == '\t' ||
               text[n - 1] == '\r' || text[n - 1] == '\n'))
    text[--n] = 0;
  return text;
}
bool ChineseProfile_SetDefaultLanguage(const char *ini_path, char *error,
                                       size_t error_size) {
  if (error && error_size) error[0] = 0;
  char marker[1024];
  if (!suffix(marker, ini_path, ".cn-default-v1", error, error_size))
    return false;
  if (!recover(ini_path, error, error_size)) return false;
  if (regular(marker)) return true;
  uint8_t *input = NULL, *output = NULL;
  size_t size = 0, pos = 0, used = 0;
  if (!read_file(ini_path, 65536, &input, &size, error, error_size))
    return false;
  bool ok = false, general = false, inserted = false;
  if (memchr(input, 0, size)) {
    fail(error, error_size, "Chinese migration INI contains NUL", ini_path);
    goto done;
  }
  output = malloc(size + 64);
  if (!output) {
    fail(error, error_size, "Chinese migration allocation failed", ini_path);
    goto done;
  }
  while (pos < size) {
    size_t end = pos;
    while (end < size && input[end] != '\n') end++;
    if (end < size) end++;
    size_t n = end - pos;
    char parsed[1024];
    if (n >= sizeof(parsed)) {
      fail(error, error_size, "Chinese migration INI line too long", ini_path);
      goto done;
    }
    memcpy(parsed, input + pos, n);
    parsed[n] = 0;
    char *text = trim(parsed);
    bool skip = false;
    if (text[0] == '[') {
      general = strcasecmp(text, "[General]") == 0;
      if (general && !inserted) {
        const char *header = "[General]\nLanguage = cn\n";
        memcpy(output + used, header, strlen(header));
        used += strlen(header);
        inserted = true;
        skip = true;
      }
    }
    char *equals = strchr(text, '=');
    if (general && equals) {
      *equals = 0;
      if (!strcasecmp(trim(text), "Language")) skip = true;
    }
    if (!skip) {
      memcpy(output + used, input + pos, n);
      used += n;
    }
    pos = end;
  }
  if (!inserted) {
    const char *header = "\n[General]\nLanguage = cn\n";
    memcpy(output + used, header, strlen(header));
    used += strlen(header);
  }
  if (!replace(ini_path, output, used, error, error_size)) goto done;
  ok = replace(marker, (const uint8_t *)"1\n", 2, error, error_size);
done:
  free(input);
  free(output);
  return ok;
}
