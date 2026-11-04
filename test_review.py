"""Independent hand-built RIFF regressions for the November 1 review."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from audit import audit, inspect_wav, sample_time, Invalid


def chunk(tag, data, pad=True):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data)%2 and pad else b'')

def wav(bits=16, channels=1, fmt_length=16, changes=None, duplicate=False, before=False, after=False):
    width=bits//8; pcm=bytes((i%256 for i in range(5*channels*width)))
    fields=[1,channels,20000,20000*channels*width,channels*width,bits]
    for index,value in (changes or {}).items():fields[index]=value
    fmt=struct.pack('<HHIIHH',*fields)+(b'\0\0' if fmt_length==18 else b'')
    body=b'WAVE'+(chunk(b'JUNK',b'x') if before else b'')+chunk(b'fmt ',fmt)
    body+=chunk(b'data',pcm)+(chunk(b'fmt ',fmt) if duplicate else b'')+(chunk(b'JUNK',b'x') if after else b'')
    return b'RIFF'+struct.pack('<I',len(body))+body,pcm

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def write(self,p,value):p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    def project(self,raw=None,ident='U001',mode='pcm',content=False,retime=False):
        raw=raw or wav()[0]
        for side in ('old','new'):
            d=self.root/side/'audio';d.mkdir(parents=True,exist_ok=True);(d/'a.wav').write_bytes(raw)
            self.write(d/'audio_report.json',{'segments':[{'id':1,'file_id':ident,'path':'audio/a.wav','frames':5,'sample_rate':20000,'channels':1,'wav_sha256':hashlib.sha256(raw).hexdigest(),'timeline_start_seconds':0,'timeline_end_seconds':0.00025}]})
            self.write(d/'caption_timeline.json',[{'id':1,'page':1,'text':'A','start_seconds':0,'end_seconds':0.0001,'timeline_start_seconds':0,'timeline_end_seconds':0.0001},{'id':1,'page':2,'text':'B','start_seconds':0.0001,'end_seconds':0.00025,'timeline_start_seconds':0.0001,'timeline_end_seconds':0.00025}])
        self.policy={'version':2,'allow_audio_content_ids':[ident] if content else [],'allow_audio_duration_ids':[],'allow_caption_retime_ids':[ident] if retime else [],'audio_equality':mode}
        self.write(self.root/'policy.json',self.policy)
    def run_audit(self):return audit(self.root/'old',self.root/'new',self.root/'policy.json')
    def change_wav(self,raw,update=True):
        d=self.root/'new/audio';(d/'a.wav').write_bytes(raw)
        if update:
            x=json.loads((d/'audio_report.json').read_text(encoding='utf-8'));x['segments'][0]['wav_sha256']=hashlib.sha256(raw).hexdigest();self.write(d/'audio_report.json',x)
    def retime(self):
        p=self.root/'new/audio/caption_timeline.json';x=json.loads(p.read_text(encoding='utf-8'));x[0]['end_seconds']=x[0]['timeline_end_seconds']=0.00015;x[1]['start_seconds']=x[1]['timeline_start_seconds']=0.00015;self.write(p,x)
    def test_handmade_geometry_and_fmt_lengths(self):
        for bits in (8,16,24,32):
            for channels in (1,2):
                for length in (16,18):
                    raw,pcm=wav(bits,channels,length,before=True,after=True);p=self.root/'case.wav';p.write_bytes(raw);r=inspect_wav(p)
                    self.assertEqual(r['frames'],5);self.assertEqual(r['pcm_sha256'],hashlib.sha256(pcm).hexdigest());self.assertEqual(r['sample_width'],bits//8)
    def test_invalid_fmt_all_modes_permissions(self):
        invalid=[wav(changes={5:15})[0],wav(changes={4:1})[0],wav(changes={3:0})[0],wav(changes={0:0xfffe})[0],wav(duplicate=True)[0]]
        extended=bytearray(wav(fmt_length=18)[0]);struct.pack_into('<H',extended,36,1);invalid.append(bytes(extended))
        for raw in invalid:
            for mode in ('pcm','bytes'):
                for allowed in (False,True):
                    self.project(mode=mode,content=allowed);self.change_wav(raw)
                    self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_retime_only_does_not_allow_pcm_change(self):
        self.project(retime=True);self.retime();self.assertEqual(self.run_audit()['status'],'PASS')
        raw=bytearray((self.root/'new/audio/a.wav').read_bytes());raw[44]^=1;self.change_wav(raw)
        r=self.run_audit();self.assertEqual(r['status'],'FAIL');self.assertEqual(r['violations'],['U001: unapproved audio change'])
    def test_content_allowed_bit_change_passes(self):
        self.project(content=True,retime=True);self.retime();raw=bytearray((self.root/'new/audio/a.wav').read_bytes());raw[44]^=1;self.change_wav(raw);self.assertEqual(self.run_audit()['status'],'PASS')
    def test_bit_only_stale_or_updated_hash(self):
        for update,expected in ((False,'INCONCLUSIVE'),(True,'FAIL')):
            for mode in ('pcm','bytes'):
                self.project(mode=mode);raw=bytearray((self.root/'new/audio/a.wav').read_bytes());raw[44]^=1;self.change_wav(raw,update);self.assertEqual(self.run_audit()['status'],expected)
    def test_retime_bounds_still_invalid(self):
        self.project(retime=True);p=self.root/'new/audio/caption_timeline.json';x=json.loads(p.read_text(encoding='utf-8'));x[0]['end_seconds']=x[0]['timeline_end_seconds']=0.0003;self.write(p,x);self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_duration_still_requires_content(self):
        self.project();self.policy['allow_audio_duration_ids']=['U001'];self.write(self.root/'policy.json',self.policy);self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_effective_policy_and_metadata(self):
        for mode,expected in (('pcm','PASS'),('bytes','FAIL')):
            self.project(mode=mode);self.change_wav(wav(after=True)[0]);r=self.run_audit();self.assertEqual(r['status'],expected);self.assertEqual(r['audio_equality'],mode);self.assertEqual(r['effective_policy'],self.policy);self.assertTrue(any('extra JSON' in x for x in r['limits']))
    def test_stdout_encodings_collision_and_input_protection(self):
        for codec in ('ascii','cp932'):
            for collision in (False,True):
                self.project(ident='発話😀');files=[p for p in self.root.rglob('*') if p.is_file()];before={p:p.read_bytes() for p in files}
                cmd=[sys.executable,str(Path(__file__).with_name('audit.py')),str(self.root/'old'),str(self.root/'new'),str(self.root/'policy.json')]
                if collision:cmd+=['--output',str(self.root/'policy.json')]
                run=subprocess.run(cmd,capture_output=True,env=dict(os.environ,PYTHONIOENCODING=codec));r=json.loads(run.stdout.decode('ascii'));self.assertEqual(run.returncode,2 if collision else 0);self.assertEqual(r['status'],'INCONCLUSIVE' if collision else 'PASS');self.assertEqual(before,{p:p.read_bytes() for p in files})
    def test_huge_coordinates_through_cli(self):
        self.project()
        for side in ('old','new'):
            d=self.root/side/'audio'
            for name in ('audio_report.json','caption_timeline.json'):
                x=json.loads((d/name).read_text(encoding='utf-8'))
                rows=x['segments'] if isinstance(x,dict) else x
                for row in rows:
                    for key in ('timeline_start_seconds','timeline_end_seconds'):
                        val=row[key]
                        row[key]='EXACT:'+str(10**24)+{0:'.00000',0.0001:'.00010',0.00025:'.00025'}[val]
                import re
                text=json.dumps(x);text=re.sub(r'"EXACT:([0-9.]+)"',r'\1',text);(d/name).write_text(text)
        cmd=[sys.executable,str(Path(__file__).with_name('audit.py')),str(self.root/'old'),str(self.root/'new'),str(self.root/'policy.json')]
        run=subprocess.run(cmd,capture_output=True);self.assertEqual(run.returncode,0);self.assertEqual(json.loads(run.stdout)['status'],'PASS')
        for name in ('audio_report.json','caption_timeline.json'):
            p=self.root/'new/audio'/name;s=p.read_text(encoding='utf-8').replace(str(10**24)+'.00000',str(10**24)+'.00005').replace(str(10**24)+'.00010',str(10**24)+'.00015').replace(str(10**24)+'.00025',str(10**24)+'.00030');p.write_text(s)
        run=subprocess.run(cmd,capture_output=True);self.assertEqual(run.returncode,1);self.assertEqual(json.loads(run.stdout)['status'],'FAIL')
    def test_tolerance_boundaries_exact(self):
        for value in ('1.000000000045','1.000000000050','0.999999999950','0.999999999955'):
            self.assertEqual(sample_time(Decimal(value),20000),20000)
        for value in ('1.000000000050000000000001','0.999999999949999999999999'):
            with self.assertRaises(Invalid):sample_time(Decimal(value),20000)
        with localcontext() as c:
            c.prec=6
            self.assertEqual(sample_time(Decimal('1000000000000000000000000.00005'),20000),20000*10**24+1)
