#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
static FILE *writer;
static int renames;
static int fault(const char *name) {
  const char *value = getenv("CN_FAULT");
  return value && !strcmp(value, name);
}
FILE *CnTestOpen(const char *path, const char *mode) {
  if (strchr(mode, 'w') && fault("open")) {
    errno = ENOSPC;
    return NULL;
  }
  FILE *f = fopen(path, mode);
  if (f && strchr(mode, 'w')) writer = f;
  return f;
}
size_t CnTestWrite(const void *p, size_t size, size_t count, FILE *f) {
  if (f == writer && fault("write")) {
    errno = ENOSPC;
    return count ? fwrite(p, size, count - 1, f) : 0;
  }
  return fwrite(p, size, count, f);
}
int CnTestClose(FILE *f) {
  int was_writer = f == writer;
  int result = fclose(f);
  if (was_writer) writer = NULL;
  if (was_writer && fault("close")) {
    errno = EIO;
    return EOF;
  }
  return result;
}
int CnTestRename(const char *from, const char *to) {
  renames++;
  if ((renames == 1 && fault("rename1")) ||
      (renames == 2 && (fault("rename2") || fault("rename2+3"))) ||
      (renames == 3 && fault("rename2+3"))) {
    errno = EIO;
    return -1;
  }
  struct stat st;
  if (!stat(to, &st)) {
    errno = EEXIST;
    return -1;
  }
  return rename(from, to);
}
