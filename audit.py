#!/usr/bin/env python3
"""Experimental material-only audit for one audio_report/caption_timeline format."""
import argparse
from decimal import Decimal, DecimalException
import hashlib
import json
from pathlib import Path
import sys
import struct
import wave


class Invalid(ValueError):
    pass


def unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid('duplicate JSON key')
        out[k] = v
    return out


def read_json(p):
    return json.loads(p.read_text(encoding='utf-8'), parse_float=Decimal, object_pairs_hook=unique)


def integer(v):
    return type(v) is int


def valid_text(value):
    return isinstance(value, str) and bool(value) and '\x00' not in value and bool(value.encode('utf-8', errors='strict'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_file(root, rel):
    if not isinstance(rel, str) or not rel or '\\' in rel or ':' in rel:
        raise Invalid('invalid relative material path')
    p = Path(rel)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != rel:
        raise Invalid('noncanonical relative material path')
    out = (root / p).resolve()
    if not out.is_relative_to(root) or not out.is_file():
        raise Invalid('missing material or escaping symlink')
    return out


def sample_time(value, rate):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise Invalid('timestamp must be a finite JSON number')
    value = Decimal(value)
    if not value.is_finite():
        raise Invalid('timestamp must be finite')
    if not integer(rate) or rate <= 0:
        raise Invalid('sample rate must be a positive integer')
    numerator, denominator = value.as_integer_ratio()
    numerator *= rate
    # Integer arithmetic avoids Decimal context rounding at large coordinates.
    n, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and n % 2):
        n += 1
    if abs(numerator - n * denominator) * 1000000 > denominator or n < 0:
        raise Invalid('timestamp is not on the sample grid')
    return n


def pcm_data_size(path):
    """Inspect RIFF chunk bounds without loading payloads or relying on wave internals."""
    with path.open('rb') as source:
        size = source.seek(0, 2)
        source.seek(0)
        header = source.read(12)
        if len(header) != 12 or header[:4] != b'RIFF' or header[8:] != b'WAVE':
            raise Invalid('invalid RIFF WAVE header')
        end = 8 + struct.unpack('<I', header[4:8])[0]
        if end < 12 or end > size:
            raise Invalid('truncated RIFF container')
        position = 12
        data_size = None
        fmt_seen = False
        while position < end:
            if end - position < 8:
                raise Invalid('truncated RIFF chunk header')
            source.seek(position)
            tag, length = struct.unpack('<4sI', source.read(8))
            chunk_end = position + 8 + length
            if chunk_end > end:
                raise Invalid('truncated RIFF chunk')
            if tag == b'fmt ':
                if fmt_seen or data_size is not None or length not in (16, 18):
                    raise Invalid('unsupported or ambiguous fmt chunk')
                fmt_seen = True
                payload = source.read(length)
                tag_code, channels, rate, byte_rate, alignment, bits = struct.unpack('<HHIIHH', payload[:16])
                if tag_code != 1 or channels not in (1, 2) or rate <= 0 or bits not in (8, 16, 24, 32):
                    raise Invalid('only ordinary 8/16/24/32-bit mono/stereo PCM is supported')
                if alignment != channels * (bits // 8) or byte_rate != rate * alignment:
                    raise Invalid('inconsistent PCM fmt geometry')
                if length == 18 and payload[16:] != b'\x00\x00':
                    raise Invalid('ordinary PCM extension must be empty')
            if tag == b'data':
                if not fmt_seen:
                    raise Invalid('PCM data precedes fmt')
                if data_size is not None:
                    raise Invalid('multiple PCM data chunks unsupported')
                data_size = length
            # wave's writer may omit padding for an odd final payload.
            position = chunk_end if chunk_end == end else chunk_end + (length % 2)
        if data_size is None:
            raise Invalid('missing PCM data chunk')
        return data_size


def inspect_wav(path):
    if path.suffix.lower() != '.wav':
        raise Invalid('only PCM WAV is supported')
    declared_pcm_bytes = pcm_data_size(path)
    byte_digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            byte_digest.update(chunk)
    with wave.open(str(path), 'rb') as w:
        frames, rate, channels, width = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        if w.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (1, 2, 3, 4) or frames <= 0 or rate <= 0:
            raise Invalid('unsupported PCM geometry')
        if declared_pcm_bytes % (channels * width) or declared_pcm_bytes != frames * channels * width:
            raise Invalid('incomplete PCM frame')
        pcm_digest = hashlib.sha256()
        remaining = frames
        pcm_bytes = 0
        while remaining:
            chunk = w.readframes(min(remaining, 65536))
            if not chunk:
                raise Invalid('truncated PCM data')
            if len(chunk) % (channels * width):
                raise Invalid('incomplete PCM frame')
            pcm_digest.update(chunk)
            pcm_bytes += len(chunk)
            remaining -= len(chunk) // (channels * width)
        if pcm_bytes != frames * channels * width:
            raise Invalid('truncated PCM data')
    return dict(frames=frames, sample_rate=rate, channels=channels, sample_width=width,
                byte_sha256=byte_digest.hexdigest(), pcm_sha256=pcm_digest.hexdigest())


def load_project(root):
    root = Path(root).resolve()
    report_path = safe_file(root, 'audio/audio_report.json')
    caption_path = safe_file(root, 'audio/caption_timeline.json')
    doc, caps = read_json(report_path), read_json(caption_path)
    if not isinstance(doc, dict) or not isinstance(doc.get('segments'), list) or not doc['segments']:
        raise Invalid('audio_report needs nonempty segments')
    if not isinstance(caps, list) or not caps:
        raise Invalid('caption_timeline needs nonempty pages')
    result = dict(audio=[], captions=[], source_hashes={'audio_report': sha(report_path.read_bytes()), 'caption_timeline': sha(caption_path.read_bytes())})
    ids, paths, numeric_ids = set(), set(), {}
    common_rate = None
    last_end = -1
    for s in doc['segments']:
        if not isinstance(s, dict):
            raise Invalid('segment must be an object')
        ident = s['file_id']
        if not valid_text(ident) or any(x in ident for x in '*?[]') or ident in ids:
            raise Invalid('invalid or duplicate stable audio ID')
        if not integer(s['id']) or s['id'] in numeric_ids:
            raise Invalid('invalid or duplicate numeric audio ID')
        p = safe_file(root, s['path'])
        if p in paths:
            raise Invalid('duplicate material path')
        paths.add(p)
        fp = inspect_wav(p)
        rate = fp['sample_rate']
        if common_rate is None:
            common_rate = rate
        if rate != common_rate:
            raise Invalid('mixed sample rates are unsupported')
        for field in ('frames', 'sample_rate', 'channels'):
            if not integer(s[field]) or s[field] != fp[field]:
                raise Invalid('declared WAV geometry disagrees with file')
        if s['wav_sha256'] != fp['byte_sha256']:
            raise Invalid('declared WAV hash disagrees with file')
        start = sample_time(s['timeline_start_seconds'], rate)
        end = sample_time(s['timeline_end_seconds'], rate)
        if start < last_end or end - start != fp['frames']:
            raise Invalid('audio boundaries/order/duration invalid')
        last_end = end
        item = dict(id=ident, numeric_id=s['id'], start_sample=start, end_sample=end, **fp)
        result['audio'].append(item)
        numeric_ids[s['id']] = item
        ids.add(ident)
    seen = set()
    last_global_end = -1
    page_numbers = {}
    for c in caps:
        if not isinstance(c, dict) or not integer(c['id']) or c['id'] not in numeric_ids or not integer(c['page']) or c['page'] < 1 or not valid_text(c['text']):
            raise Invalid('invalid caption identity/text')
        audio = numeric_ids[c['id']]
        key = (audio['id'], c['page'])
        if key in seen or c['page'] != page_numbers.get(audio['id'], 0) + 1:
            raise Invalid('duplicate or noncontiguous caption page')
        page_numbers[audio['id']] = c['page']
        seen.add(key)
        a, b = sample_time(c['start_seconds'], common_rate), sample_time(c['end_seconds'], common_rate)
        ga, gb = sample_time(c['timeline_start_seconds'], common_rate), sample_time(c['timeline_end_seconds'], common_rate)
        if b <= a or b > audio['frames'] or ga != audio['start_sample'] + a or gb != audio['start_sample'] + b or ga < last_global_end:
            raise Invalid('caption bounds/global-relative coordinates disagree')
        last_global_end = gb
        result['captions'].append(dict(audio_id=audio['id'], page=c['page'], text=c['text'], start_sample=a, end_sample=b, global_start_sample=ga, global_end_sample=gb))
    if set(page_numbers) != ids:
        raise Invalid('caption pages missing for an audio segment')
    result['sample_rate'] = common_rate
    return result


def policy_read(path, ids):
    p = read_json(Path(path))
    fields = {'version', 'allow_audio_content_ids', 'allow_audio_duration_ids', 'allow_caption_retime_ids', 'audio_equality'}
    if not isinstance(p, dict) or set(p) != fields or not integer(p['version']) or p['version'] != 2 or p['audio_equality'] not in ('bytes', 'pcm'):
        raise Invalid('invalid version 2 policy')
    for k in fields - {'version', 'audio_equality'}:
        values = p[k]
        if not isinstance(values, list) or any(not valid_text(x) or any(c in x for c in '*?[]') for x in values) or len(values) != len(set(values)) or not set(values).issubset(ids):
            raise Invalid('policy IDs must be unique exact known IDs')
    if not set(p['allow_audio_duration_ids']).issubset(p['allow_audio_content_ids']):
        raise Invalid('duration permission must be a subset of audio content permission')
    return p


def audit(before, after, policy):
    r = dict(version='0.3-candidate', status='INCONCLUSIVE', scope='one audio material timeline and displayed caption JSON; SRT/final render unsupported', violations=[], unknowns=[], audio=[], captions=[], limits=['Allowed edits do not certify pronunciation or caption alignment.', 'Correct baseline selection and unlisted assets are not verified.', 'Only caption text and specified sample coordinates are checked; extra JSON fields, styles, SRT and final MP4 are uninspected.', 'audio_unchanged counts equality under audio_equality, not necessarily byte-identical files.'])
    try:
        if Path(before).resolve() == Path(after).resolve():
            raise Invalid('same project directory cannot be both versions')
        old, new = load_project(before), load_project(after)
        ids = [x['id'] for x in old['audio']]
        p = policy_read(policy, set(ids))
        r['effective_policy'] = p
        r['audio_equality'] = p['audio_equality']
        r['sources'] = {'before': old['source_hashes'], 'after': new['source_hashes'], 'policy': sha(Path(policy).read_bytes())}
        if old['sample_rate'] != new['sample_rate']:
            raise Invalid('cross-version sample rate changed')
        if ids != [x['id'] for x in new['audio']]:
            raise Invalid('audio IDs/order differ; comparison not aligned')
        r['sample_rate'] = old['sample_rate']
        delta = 0
        for a, b in zip(old['audio'], new['audio']):
            ident = a['id']
            content_equal = a['byte_sha256'] == b['byte_sha256'] if p['audio_equality'] == 'bytes' else a['pcm_sha256'] == b['pcm_sha256'] and a['sample_width'] == b['sample_width']
            if b['start_sample'] != a['start_sample'] + delta:
                r['violations'].append(f'{ident}: start does not follow exact prior permitted duration deltas')
            d = b['frames'] - a['frames']
            if d and ident not in p['allow_audio_duration_ids']:
                r['violations'].append(f'{ident}: unapproved duration change')
            if not content_equal and ident not in p['allow_audio_content_ids']:
                r['violations'].append(f'{ident}: unapproved audio change')
            if any(a[k] != b[k] for k in ('channels', 'sample_width')):
                r['violations'].append(f'{ident}: audio geometry change')
            r['audio'].append(dict(id=ident, content_equal=content_equal, duration_delta_samples=d, expected_prior_delta_samples=delta))
            if ident in p['allow_audio_duration_ids']:
                delta += d
        keys = lambda pages: [(x['audio_id'], x['page']) for x in pages]
        if keys(old['captions']) != keys(new['captions']):
            raise Invalid('caption identities/count/order differ')
        for a, b in zip(old['captions'], new['captions']):
            ident = a['audio_id']
            text_equal = a['text'] == b['text']
            local_equal = a['start_sample'] == b['start_sample'] and a['end_sample'] == b['end_sample']
            if not text_equal:
                r['violations'].append(f'{ident}/page{a["page"]}: displayed caption changed')
            if not local_equal and ident not in p['allow_caption_retime_ids']:
                r['violations'].append(f'{ident}/page{a["page"]}: unapproved local caption retiming')
            r['captions'].append(dict(audio_id=ident, page=a['page'], text_equal=text_equal, local_time_equal=local_equal))
        r['summary'] = dict(audio_count=len(r['audio']), audio_unchanged=sum(x['content_equal'] for x in r['audio']), caption_pages=len(r['captions']), caption_text_unchanged=sum(x['text_equal'] for x in r['captions']), permitted_total_delta_samples=delta)
        r['status'] = 'FAIL' if r['violations'] else 'PASS'
    except (Invalid, ValueError, OSError, RuntimeError, KeyError, TypeError, EOFError, DecimalException, wave.Error) as e:
        r['unknowns'].append(str(e) if isinstance(e, Invalid) else type(e).__name__ + ': material verification unavailable')
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before_project')
    p.add_argument('after_project')
    p.add_argument('policy')
    p.add_argument('--output')
    args = p.parse_args()
    r = audit(args.before_project, args.after_project, args.policy)
    if args.output:
        try:
            with Path(args.output).open('x', encoding='utf-8') as f:
                json.dump(r, f, indent=2, ensure_ascii=False)
                f.write('\n')
        except (OSError, RuntimeError):
            r['status'] = 'INCONCLUSIVE'
            r['unknowns'].append('Output not saved; existing files are never overwritten.')
            print(json.dumps(r, ensure_ascii=True, indent=2))
    else:
        print(json.dumps(r, ensure_ascii=True, indent=2))
    return {'PASS': 0, 'FAIL': 1, 'INCONCLUSIVE': 2}[r['status']]


if __name__ == '__main__':
    sys.exit(main())
