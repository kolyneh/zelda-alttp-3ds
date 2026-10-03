#!/usr/bin/env python3
"""Exercise the actual boot boundary with production CN migration and synthetic assets."""
from pathlib import Path
import os
import subprocess
import tempfile
from run_chinese_tests import make_assets
ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'platform/3ds/source/platform_3ds.c').read_text()
def function(signature):
    a=source.index(signature);end=source.index('{',a)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[a:end]+'\n'
code=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>
#include "chinese_profile.h"
#include "chinese_assets.h"
#define LogSetup(...) do {printf(__VA_ARGS__);putchar('\n');} while(0)
static const char *kBundledConfig="bundled.ini",*kProfilesDirectory="profiles";
static const char *kAssetsFilename="zelda3_assets.dat",*kBundledChinesePack;
static const char *g_profile_prepare_status;
typedef struct {char filename[256],profile[256];uint32_t hash;} RomEntry;
static int extract_calls,selected_writes;
'''
for signature in ['static bool ProfileSetupFailure(', 'static bool IsRegularFile(const char *path) {',
                  'static bool EnsureDirectory(const char *path) {', 'static char *Trim(',
                  'static bool CopyFileIfMissing(', 'static bool CopyFileReplacing(const char *source, const char *destination) {',
                  'static bool MigrateWideDefaults(', 'static void LogProfileLanguage(']:code+=function(signature)
code+=r'''
// Synthetic extractor stands at the successful BPS boundary. Storage and CN
// code below are production functions; the test needs no ROM or console.
static bool AssetsFileLooksValid(const char *path) {
 FILE *f=fopen(path,"rb");if(!f)return false;
 char header[15]={0};bool ok=fread(header,1,14,f)==14 && !memcmp(header,"Zelda3_v0      ",14);fclose(f);return ok;
}
static bool ExtractAssetsFromRom(const char *path) {
 extract_calls++;return CopyFileReplacing("../../fixture.dat",kAssetsFilename);
}
static bool PrepareSaveDirectory(const RomEntry *rom,bool legacy){return true;}
static void WriteSelectedRom(const RomEntry *rom){selected_writes++;}
'''+function('static bool EnsureProfileReady(')+r'''
int main(int argc,char **argv) {
 assert(argc==3);kBundledChinesePack=argv[1];RomEntry rom={0};
 strcpy(rom.filename,"game.sfc");strcpy(rom.profile,"profiles/fixture");
 assert(EnsureProfileReady(&rom,false));assert(selected_writes==1);assert(extract_calls==atoi(argv[2]));
 return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    p=Path(directory);c=p/'test.c';c.write_text(code);source_dir=ROOT/'platform/3ds/source';exe=p/'test'
    subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-include',
                    str(ROOT/'platform/3ds/tests/chinese_profile_faults.h'),'-I',str(source_dir),
                    '-c',str(c),'-o',str(p/'boot.o')],check=True)
    subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-include',
                    str(ROOT/'platform/3ds/tests/chinese_profile_faults.h'),'-I',str(source_dir),
                    '-c',str(source_dir/'chinese_profile.c'),'-o',str(p/'profile.o')],check=True)
    subprocess.run(['cc','-g','-fsanitize=address,undefined',str(p/'boot.o'),str(p/'profile.o'),
                    str(source_dir/'chinese_assets.c'),str(ROOT/'platform/3ds/tests/chinese_profile_faults.c'),
                    '-o',str(exe)],check=True)
    (p/'fixture.dat').write_bytes(make_assets());(p/'bundled.ini').write_text('[General]\nLanguage = cn\n')
    saves=p/'saves';saves.mkdir();save=saves/'fixture.srm';save.write_bytes(bytes(range(256))*32)
    original_save=save.read_bytes();pack=ROOT/'build-3ds/chinese/zelda3_cn.pack'
    env={**os.environ,'UBSAN_OPTIONS':'halt_on_error=1'}
    subprocess.run([str(exe),str(pack),'1'],cwd=p,env=env,check=True)
    profile=p/'profiles/fixture';assets=profile/'zelda3_assets.dat';ini=profile/'zelda3.ini'
    first=assets.read_bytes();assert len(first)>len((p/'fixture.dat').read_bytes())
    assert (p/'zelda3_assets.dat').read_bytes()==first
    ini.write_text(ini.read_text().replace('Language = cn','Language = us'))
    subprocess.run([str(exe),str(pack),'0'],cwd=p,env=env,check=True)
    assert assets.read_bytes()==first;assert 'Language = us' in (p/'zelda3.ini').read_text()
    assets.rename(Path(str(assets)+'.cn.bak'))
    subprocess.run([str(exe),str(pack),'0'],cwd=p,env=env,check=True)
    assert assets.read_bytes()==first;assert not Path(str(assets)+'.cn.bak').exists()
    assert save.read_bytes()==original_save
print('PASS BPS-success boundary, cached CN reuse, interrupted promotion before extraction, preserved English choice and SRAM')
