#!/usr/bin/env python3
"""Run actual SD-compatible migration code, including interrupted transactions."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from run_chinese_tests import make_assets, get_slots, pack_arrays, unpack_table
ROOT=Path(__file__).resolve().parents[3]

class ChineseProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.directory=Path(cls.temp.name);cls.exe=cls.directory/'test'
        source=ROOT/'platform/3ds/source';tests=ROOT/'platform/3ds/tests'
        # Inject file failures only into the production migration module.
        obj=cls.directory/'profile.o'
        subprocess.run(['cc','-std=c11','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                        '-include',str(tests/'chinese_profile_faults.h'),'-I',str(source),
                        '-c',str(source/'chinese_profile.c'),'-o',str(obj)],check=True)
        subprocess.run(['cc','-std=c11','-g','-fsanitize=address,undefined','-I',str(source),str(obj),
                        str(source/'chinese_assets.c'),str(tests/'chinese_profile_faults.c'),
                        str(tests/'chinese_profile_test.c'),'-o',str(cls.exe)],check=True)
        cls.pack=ROOT/'build-3ds/chinese/zelda3_cn.pack'
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_module(self,path,expected=1,mode='assets',fault=None,pack=None):
        env={**os.environ,'UBSAN_OPTIONS':'halt_on_error=1'}
        if fault:env['CN_FAULT']=fault
        subprocess.run([str(self.exe),mode,str(path),str(pack or self.pack),str(expected)],env=env,check=True)
    def test_cache_migration_reuse_update_and_language_coexistence(self):
        p=self.directory/'cached.dat';p.write_bytes(make_assets());original=get_slots(p.read_bytes())
        self.run_module(p);new=p.read_bytes();self.run_module(p,0);self.assertEqual(new,p.read_bytes())
        slots=get_slots(new);dialogs=unpack_table(slots[94]);dialogs[1]=b'old Chinese';dialogs.append(b'French fixture')
        fonts=unpack_table(slots[95]);fonts.append(b'French font')
        mappings=unpack_table(slots[96]);mappings.append(pack_arrays([b'fr',b'\2\2\2']))
        slots[94:97]=map(pack_arrays,(dialogs,fonts,mappings));p.write_bytes(make_assets(slots))
        self.run_module(p);slots=get_slots(p.read_bytes())
        self.assertEqual(unpack_table(slots[94])[2],b'French fixture');self.assertEqual(len(unpack_table(slots[96])),3)
        for i in range(165):
            if i not in (94,95,96):self.assertEqual(slots[i],original[i])
    def test_failed_storage_keeps_complete_old_assets_and_recovers(self):
        for fault in ('open','write','close','rename1','rename2','rename2+3'):
            with self.subTest(fault=fault):
                p=self.directory/(fault+'.dat');old=make_assets();p.write_bytes(old)
                self.run_module(p,-1,fault=fault);backup=Path(str(p)+'.cn.bak')
                self.assertTrue((p.exists() and p.read_bytes()==old) or (backup.exists() and backup.read_bytes()==old))
                self.run_module(p);self.run_module(p,0);self.assertFalse(backup.exists())
                self.assertFalse(Path(str(p)+'.cn.tmp').exists())
    def test_bad_pack_does_not_change_existing_cache(self):
        p=self.directory/'invalid.dat';old=make_assets();p.write_bytes(old)
        pack=self.directory/'bad.pack';pack.write_bytes(b'invalid pack')
        self.run_module(p,-1,pack=pack);self.assertEqual(p.read_bytes(),old)
        self.run_module(self.directory/'absent.dat',-1)
        huge=self.directory/'huge.pack'
        with huge.open('wb') as f:f.truncate(1048577)
        self.run_module(p,-1,pack=huge);self.assertEqual(p.read_bytes(),old)
    def test_interrupted_promotion_is_recovered(self):
        p=self.directory/'interrupted.dat';backup=Path(str(p)+'.cn.bak');backup.write_bytes(make_assets())
        self.run_module(p);self.assertTrue(p.exists());self.assertFalse(backup.exists())
    def test_one_time_default_preserves_other_settings_and_later_english_choice(self):
        original='[General]\nLanguage = us\nDisplayMode = Original\n[Sound]\nEnableAudio = 0\n[General]\nLanguage = fr\n'
        for name, text in [('normal',original),('no-general','[Sound]\nEnableAudio = 0\n'),('fresh','[General]\nAutosave = 1\n')]:
            p=self.directory/(name+'.ini');p.write_text(text);self.run_module(p,mode='ini')
            result=p.read_text();self.assertEqual(result.count('Language = cn'),1)
            self.assertNotIn('Language = us',result);self.assertNotIn('Language = fr',result)
            if name=='normal':self.assertIn('DisplayMode = Original',result)
            if name!='fresh':self.assertIn('EnableAudio = 0',result)
            p.write_text(result.replace('Language = cn','Language = us'))
            self.run_module(p,mode='ini');self.assertIn('Language = us',p.read_text());self.assertNotIn('Language = cn',p.read_text())
    def test_ini_storage_failure_preserves_old_settings_and_retries(self):
        for fault in ('open','write','close','rename1','rename2','rename2+3'):
            p=self.directory/(fault+'.ini');old='[General]\nLanguage = us\nDisplayMode = Original\n';p.write_text(old)
            self.run_module(p,-1,mode='ini',fault=fault)
            backup=Path(str(p)+'.cn.bak')
            self.assertTrue((p.exists() and p.read_text()==old) or (backup.exists() and backup.read_text()==old))
            self.run_module(p,mode='ini');self.assertIn('Language = cn',p.read_text());self.assertIn('DisplayMode = Original',p.read_text())

if __name__=='__main__':unittest.main()
