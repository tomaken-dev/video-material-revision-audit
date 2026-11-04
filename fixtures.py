import hashlib
import json
import math
from pathlib import Path
import struct
import wave


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_project(root, n=59, changed=()):
    root = Path(root)
    root.mkdir(parents=True)
    (root/'audio').mkdir()
    segments, captions = [], []
    cursor = 0
    for i in range(1, n+1):
        ident = f'U{i:03}'
        frames = 2399 + i + (111 if i in changed else 0)
        frequency = 660 if i in changed else 440
        data = b''.join(struct.pack('<h', int(10000*math.sin(2*math.pi*frequency*x/24000))) for x in range(frames))
        path = root/'audio'/f'{ident}.wav'
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data)
        segments.append(dict(id=i,file_id=ident,path=f'audio/{ident}.wav',frames=frames,sample_rate=24000,channels=1,
                             timeline_start_seconds=cursor/24000,timeline_end_seconds=(cursor+frames)/24000,
                             wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        # 55 two-page utterances + four one-page utterances = 114 pages.
        boundaries = [0,frames//2,frames] if i <= n-4 else [0,frames]
        for page,(start,end) in enumerate(zip(boundaries,boundaries[1:]),1):
            captions.append(dict(id=i,page=page,text=f'合成の発話{i}・字幕{page}',start_seconds=start/24000,end_seconds=end/24000,
                                 timeline_start_seconds=(cursor+start)/24000,timeline_end_seconds=(cursor+end)/24000))
        cursor += frames
    dump(root/'audio/audio_report.json',dict(segments=segments))
    dump(root/'audio/caption_timeline.json',captions)


def generate(root, n=59):
    root = Path(root)
    if root.exists():
        raise ValueError('destination exists')
    changed = (34,46) if n >= 46 else (1,2)
    make_project(root/'修正前',n)
    make_project(root/'修正後',n,changed)
    ids = [f'U{x:03}' for x in changed]
    dump(root/'policy.json',dict(version=2,allow_audio_content_ids=ids,allow_audio_duration_ids=ids,allow_caption_retime_ids=ids,audio_equality='bytes'))
    return root/'修正前',root/'修正後',root/'policy.json'


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('destination');generate(p.parse_args().destination)
