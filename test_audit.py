import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import hashlib
import wave
import struct
from unittest.mock import patch
from audit import audit,load_project,sample_time,inspect_wav,Invalid
from decimal import Decimal
from fixtures import generate,dump


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'日本語'
        self.old,self.new,self.policy=generate(self.root,5)
    def tearDown(self):self.tmp.cleanup()
    def run_audit(self):return audit(self.old,self.new,self.policy)
    def edit(self,path,fn):
        d=json.loads(path.read_text(encoding='utf-8'));fn(d);dump(path,d)
    def test_report_version(self):
        self.assertEqual(self.run_audit()['version'], '0.3-candidate')
        self.assertEqual(audit(self.old,self.old,self.policy)['version'], '0.3-candidate')
    def test_allowed_duration_and_shift(self):
        r=self.run_audit();self.assertEqual(r['status'],'PASS');self.assertEqual(r['summary']['permitted_total_delta_samples'],222)
    def test_noninteger_ms(self):
        p=load_project(self.old);self.assertEqual(p['audio'][1]['frames'],2401)
    def test_one_sample_precision(self):
        self.assertEqual(sample_time(Decimal('0.10004166666666667'),24000),2401)
        with self.assertRaises(Invalid):sample_time(Decimal('0.10005'),24000)
    def test_duration_permission_required(self):
        self.edit(self.policy,lambda d:d.update(allow_audio_duration_ids=[]));self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_retime_permission_required(self):
        self.edit(self.policy,lambda d:d.update(allow_caption_retime_ids=[]));self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_unapproved_content(self):
        self.edit(self.policy,lambda d:d.update(allow_audio_content_ids=[],allow_audio_duration_ids=[],allow_caption_retime_ids=[]));self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_caption_text(self):
        self.edit(self.new/'audio/caption_timeline.json',lambda d:d[0].update(text='違う本文'));self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_stale_global_caption(self):
        self.edit(self.new/'audio/caption_timeline.json',lambda d:d[2].update(timeline_start_seconds=d[2]['timeline_start_seconds']+1/24000));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_one_sample_unauthorized_shift(self):
        def shift(d):
            for s in d['segments']:
                s['timeline_start_seconds']+=1/24000;s['timeline_end_seconds']+=1/24000
        def caps(d):
            for c in d:
                c['timeline_start_seconds']+=1/24000;c['timeline_end_seconds']+=1/24000
        self.edit(self.new/'audio/audio_report.json',shift);self.edit(self.new/'audio/caption_timeline.json',caps)
        self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_local_unapproved_one_sample(self):
        def change(d):
            c=d[-1];c['start_seconds']+=1/24000;c['timeline_start_seconds']+=1/24000
        self.edit(self.new/'audio/caption_timeline.json',change);self.assertEqual(self.run_audit()['status'],'FAIL')
    def test_missing(self):
        (self.new/'audio/U003.wav').unlink();self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_missing_page(self):
        self.edit(self.new/'audio/caption_timeline.json',lambda d:d.pop());self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_duplicate_id(self):
        self.edit(self.new/'audio/audio_report.json',lambda d:d['segments'][1].update(file_id='U001'));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_duplicate_page(self):
        self.edit(self.new/'audio/caption_timeline.json',lambda d:d.append(d[0]));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_duplicate_json_key(self):
        self.policy.write_text('{"version":2,"version":2}');self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_wildcard(self):
        self.edit(self.policy,lambda d:d.update(allow_audio_content_ids=['*']));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_missing_policy(self):
        self.policy.unlink();self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_self(self):self.assertEqual(audit(self.old,self.old,self.policy)['status'],'INCONCLUSIVE')
    def test_unchanged_distinct(self):
        shutil.rmtree(self.new);shutil.copytree(self.old,self.new);self.assertEqual(self.run_audit()['status'],'PASS')
    def test_symlink_loop(self):
        p=self.new/'audio/U003.wav';p.unlink()
        try:
            p.symlink_to(p.name)
        except OSError as exc:
            if sys.platform == 'win32' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks symlink privilege; symlink protection not tested')
            raise
        self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_streaming_wav_all_pcm_geometries(self):
        for channels in (1, 2):
            for width in (1, 2, 3, 4):
                with self.subTest(channels=channels, width=width):
                    p=self.root/'geometry.wav'
                    frames=65537
                    pcm=bytes(range(256))*(frames*channels*width//256)+bytes(range(frames*channels*width%256))
                    with wave.open(str(p),'wb') as w:
                        w.setnchannels(channels);w.setsampwidth(width);w.setframerate(24000);w.writeframes(pcm)
                    expected_bytes=hashlib.sha256(p.read_bytes()).hexdigest()
                    with patch.object(Path,'read_bytes',side_effect=AssertionError('whole-file read forbidden')):
                        r=inspect_wav(p)
                    self.assertEqual(r['byte_sha256'],expected_bytes)
                    self.assertEqual(r['pcm_sha256'],hashlib.sha256(pcm).hexdigest())
                    self.assertEqual(r['frames'],frames)
    def test_streaming_wav_truncation(self):
        p=self.old/'audio/U001.wav'
        raw=p.read_bytes();p.write_bytes(raw[:-2])
        with self.assertRaises(Invalid):inspect_wav(p)
    def test_streaming_wav_memory_bound(self):
        import tracemalloc
        p=self.root/'large.wav'
        with wave.open(str(p),'wb') as w:
            w.setnchannels(2);w.setsampwidth(4);w.setframerate(24000)
            for _ in range(32):w.writeframesraw(bytes(1024*1024))
        tracemalloc.start()
        try:
            r=inspect_wav(p)
            _,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertEqual(r['frames'],32*1024*1024//8)
        self.assertLess(peak,4*1024*1024)
    def test_partial_pcm_frame_rejected(self):
        p=self.new/'audio/U003.wav'
        raw=bytearray(p.read_bytes())
        length=struct.unpack_from('<I',raw,40)[0]
        struct.pack_into('<I',raw,40,length+1)
        raw+=b'\xff\x00'
        struct.pack_into('<I',raw,4,len(raw)-8)
        p.write_bytes(raw)
        self.edit(self.new/'audio/audio_report.json',lambda d:d['segments'][2].update(wav_sha256=hashlib.sha256(raw).hexdigest()))
        self.edit(self.policy,lambda d:d.update(audio_equality='pcm'))
        with self.assertRaises(Invalid):inspect_wav(p)
        self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_odd_8bit_pcm_with_padding(self):
        p=self.root/'odd.wav'
        with wave.open(str(p),'wb') as w:
            w.setnchannels(1);w.setsampwidth(1);w.setframerate(24000);w.writeframes(b'abc')
        raw=bytearray(p.read_bytes());raw+=b'\x00'
        struct.pack_into('<I',raw,4,len(raw)-8);p.write_bytes(raw)
        r=inspect_wav(p)
        self.assertEqual(r['frames'],3)
        self.assertEqual(r['pcm_sha256'],hashlib.sha256(b'abc').hexdigest())
    def test_riff_declared_chunk_truncation(self):
        p=self.old/'audio/U001.wav'
        raw=bytearray(p.read_bytes());struct.pack_into('<I',raw,40,len(raw)+100);p.write_bytes(raw)
        with self.assertRaises(Invalid):inspect_wav(p)
    def test_large_sample_times_remain_distinct(self):
        a=Decimal('1000000000000000000000000.00000')
        b=Decimal('1000000000000000000000000.00005')
        self.assertEqual(sample_time(a,20000),20000*10**24)
        self.assertEqual(sample_time(b,20000)-sample_time(a,20000),1)
    def test_path_escape(self):
        self.edit(self.new/'audio/audio_report.json',lambda d:d['segments'][0].update(path='../outside.wav'));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_deep_json(self):
        self.policy.write_text('['*10000+'0'+']'*10000);self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_hash_mismatch(self):
        self.edit(self.new/'audio/audio_report.json',lambda d:d['segments'][0].update(wav_sha256='bad'));self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_order(self):
        self.edit(self.new/'audio/audio_report.json',lambda d:d['segments'].reverse());self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_srt_not_accepted(self):
        (self.new/'audio/caption_timeline.json').write_text('1\n00:00:00,000 --> 00:00:01,000\ntext');self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_invalid_unicode_text(self):
        for root in (self.old,self.new):
            p=root/'audio/caption_timeline.json'
            d=json.loads(p.read_text(encoding='utf-8'));d[0]['text']='\ud800'
            p.write_text(json.dumps(d,ensure_ascii=True))
        self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_invalid_unicode_id(self):
        p=self.new/'audio/audio_report.json'
        d=json.loads(p.read_text(encoding='utf-8'));d['segments'][0]['file_id']='\ud800'
        p.write_text(json.dumps(d,ensure_ascii=True))
        self.assertEqual(self.run_audit()['status'],'INCONCLUSIVE')
    def test_output_preserves_inputs(self):
        output=self.old/'audio/audio_report.json';snapshot=output.read_bytes()
        p=subprocess.run([sys.executable,str(Path(__file__).parent/'audit.py'),str(self.old),str(self.new),str(self.policy),'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertEqual(output.read_bytes(),snapshot);self.assertEqual(json.loads(p.stdout)['status'],'INCONCLUSIVE')


if __name__=='__main__':unittest.main()
