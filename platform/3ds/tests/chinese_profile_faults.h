#include <stdio.h>
FILE *CnTestOpen(const char *, const char *);
size_t CnTestWrite(const void *, size_t, size_t, FILE *);
int CnTestClose(FILE *);
int CnTestRename(const char *, const char *);
#define fopen CnTestOpen
#define fwrite CnTestWrite
#define fclose CnTestClose
#define rename CnTestRename
