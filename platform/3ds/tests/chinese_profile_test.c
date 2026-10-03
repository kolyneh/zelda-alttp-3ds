#include "chinese_profile.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
  assert(argc == 5);
  char error[512];
  int result =
      !strcmp(argv[1], "assets")
          ? ChineseProfile_Ensure(argv[2], argv[3], error, sizeof(error))
          : (ChineseProfile_SetDefaultLanguage(argv[2], error, sizeof(error))
                 ? 1
                 : -1);
  assert(result == atoi(argv[4]));
  if (result < 0) {
    assert(error[0]);
    printf("Expected migration error: %s\n", error);
  }
  return 0;
}
