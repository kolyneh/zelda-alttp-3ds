import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/3ds/package_release.py'

def romfs_fixture(files):
    table=bytearray();data=bytearray();entries=list(files.items())
    for i,(name,value) in enumerate(entries):
        encoded=name.encode('utf-16le');next_entry=len(table)+32+((len(encoded)+3)&~3)
        table+=struct.pack('<IIQQII',0,next_entry if i+1<len(entries) else 0xffffffff,len(data),len(value),0xffffffff,len(encoded))
        table+=encoded+bytes((-len(encoded))%4);data+=value
    header=struct.pack('<10I',40,40,4,44,24,68,4,72,len(table),72+len(table))
    root=struct.pack('<6I',0,0xffffffff,0xffffffff,0,0xffffffff,0)
    return header+bytes(4)+root+bytes(4)+table+data

def cia_fixture(title):
    raw=romfs_fixture({'test.txt':b'payload'})
    ivfc=bytearray(4096);ivfc[:4]=b'IVFC';struct.pack_into('<I',ivfc,8,32);struct.pack_into('<Q',ivfc,0x44,len(raw));struct.pack_into('<I',ivfc,0x4c,12)
    romfs=ivfc+raw
    ncch=bytearray(0x400+len(romfs));ncch[:]=ncch # explicit bytearray fixture
    ncch+=bytes((-len(ncch))%512);ncch[0x100:0x104]=b'NCCH';struct.pack_into('<I',ncch,0x104,len(ncch)//512)
    struct.pack_into('<Q',ncch,0x118,title);ncch[0x18f]=4
    struct.pack_into('<II',ncch,0x1b0,2,(len(romfs)+511)//512);ncch[0x400:0x400+len(romfs)]=romfs
    tmd=bytearray(0xb34);struct.pack_into('>I',tmd,0,0x10004);struct.pack_into('>Q',tmd,0x140+0x4c,title)
    struct.pack_into('>H',tmd,0x140+0x9e,1);struct.pack_into('>Q',tmd,0xb04+8,len(ncch));tmd[0xb04+16:0xb04+48]=hashlib.sha256(ncch).digest()
    header=bytearray(0x2020);struct.pack_into('<I',header,0,len(header));struct.pack_into('<I',header,0x10,len(tmd));struct.pack_into('<Q',header,0x18,len(ncch))
    header+=bytes((-len(header))%64);content=header+tmd;content+=bytes((-len(content))%64);return bytes(content+ncch)

class PackageTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.is_file(),'Artifact verifier is missing')
        spec=importlib.util.spec_from_file_location('package_release',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_read_embedded_files_from_3dsx_and_cia(self):
        m=self.module();raw=romfs_fixture({'a.txt':b'a','b.txt':b'bb'})
        x=bytearray(44);x[:4]=b'3DSX';struct.pack_into('<H',x,4,44);struct.pack_into('<I',x,40,44)
        self.assertEqual(m.three_dsx_files(bytes(x)+raw),{'a.txt':b'a','b.txt':b'bb'})
        self.assertEqual(m.cia_files(cia_fixture(m.TITLE_ID)),{'test.txt':b'payload'})
    def test_wrong_title_corrupt_content_and_truncated_tables_fail(self):
        m=self.module()
        with self.assertRaises(ValueError):m.cia_files(cia_fixture(123))
        bad=bytearray(cia_fixture(m.TITLE_ID));bad[-1]^=1
        with self.assertRaises(ValueError):m.cia_files(bytes(bad))
        for cut in (0,39,71,103):
            with self.assertRaises(ValueError):m.romfs_files(romfs_fixture({'a.txt':b'a'})[:cut])
    def test_unlisted_rom_or_assets_cannot_be_published(self):
        m=self.module()
        for name in ('game.sfc','zelda3_assets.dat'):
            with self.assertRaises(ValueError):m.verify_files({name:b'private input'}, {})
