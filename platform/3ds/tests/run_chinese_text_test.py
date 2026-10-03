#!/usr/bin/env python3
"""Compile exact production functions, with RAM and asset fixtures, under sanitizers."""
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]
ENGINE=ROOT/'build-3ds/engine/src'

def function(source,name):
    match=re.search(r'^(?:static )?[^\n;{}]+\b'+re.escape(name)+r'\([^;]*?\)\s*\{',source,re.M)
    if not match: raise ValueError(name)
    begin=match.start();pos=source.index('{',match.start());depth=1;end=pos+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[begin:end]+'\n'

source=(ENGINE/'messaging.c').read_text();util=(ENGINE/'util.c').read_text()
constants=source[source.index('enum {\n  kTextCommandStart_US'):source.index('uint32 Text_DecodeCmd')]
preamble='''#include <assert.h>
#include <string.h>
#include "types.h"
#include "util.h"
#include "variables.h"
uint8 g_ram[131072];
struct {uint8 *sram; MemBlk dialogue_blk,dialogue_font_blk; uint8 dialogue_flags;} g_zenv;
static const uint16 kText_Positions[2]={0x6125,0x6244};
static const uint8 kVWF_RenderCharacter_setMasks[8]={0x80,0x40,0x20,0x10,8,4,2,1};
static const uint16 kVWF_RenderCharacter_renderPos[3]={0,0x2a0,0x540};
static const uint16 kVWF_RenderCharacter_linePositions[3]={0,0x40,0x80};
void VWF_RenderChinese(int);
'''
functions=['Text_DecodeCmd','Text_FilterPlayerNameCharacters','Text_WritePlayerName','Text_LoadCharacterBuffer','VWF_RenderHalf','VWF_RenderChinese','VWF_RenderSingle']
code=preamble+constants+''.join(function(util,x) for x in ['ReadLe16','ReadLe32','FindIndexInMemblk'])+''.join(function(source,x) for x in functions)+(ROOT/'platform/3ds/tests/chinese_text_test.c').read_text()
with tempfile.TemporaryDirectory() as t:
    path=Path(t)/'test.c';path.write_text(code);(ROOT/'build-3ds/chinese_text_fixture.c').write_text(code);exe=Path(t)/'test'
    subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(ENGINE),str(path),'-o',str(exe)],check=True)
    import os
    subprocess.run([str(exe), str(ROOT/'build-3ds/chinese/zelda3_cn.pack')],check=True,env={**os.environ,"UBSAN_OPTIONS":"halt_on_error=1"})
