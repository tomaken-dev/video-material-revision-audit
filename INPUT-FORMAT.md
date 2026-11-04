# Input format / 最小入力例

This is the input contract read by `audit.py`; it is not an importer. The two versions must already have corresponding stable audio IDs and the caption metadata below. This guide does not claim compatibility with arbitrary production exports.

## A complete one-audio example

Create two **different** directories, `before` and `after`, each with an `audio` subdirectory. Into each `audio` folder, copy the already-included file `synthetic_demo/修正前/audio/U001.wav` without editing it. This is a 0.1-second synthetic tone, not speech. Save the following two UTF-8 JSON files in **both** versions.

`audio/audio_report.json`:

```json
{
  "segments": [
    {
      "id": 1,
      "file_id": "U001",
      "path": "audio/U001.wav",
      "frames": 2400,
      "sample_rate": 24000,
      "channels": 1,
      "timeline_start_seconds": 0.0,
      "timeline_end_seconds": 0.1,
      "wav_sha256": "5b89461be6b44866848ba6bef985b8b277cf9ddcdfc709abfa7369acf0d029b0"
    }
  ]
}
```

`audio/caption_timeline.json`:

```json
[
  {
    "id": 1,
    "page": 1,
    "text": "Synthetic example",
    "start_seconds": 0,
    "end_seconds": 0.1,
    "timeline_start_seconds": 0,
    "timeline_end_seconds": 0.1
  }
]
```

Save this `policy.json` outside the two version folders:

```json
{
  "version": 2,
  "allow_audio_content_ids": [],
  "allow_audio_duration_ids": [],
  "allow_caption_retime_ids": [],
  "audio_equality": "bytes"
}
```

From the directory containing `audit.py`, `before`, `after` and `policy.json`, run:

```sh
python audit.py before after policy.json --output one_item_result.json
```

Use Python 3.12 and a new output filename. Expected: PASS, one unchanged audio item, one unchanged caption text, permitted duration delta zero. This verifies identical separate copies only; it is not an audio-edit example. The README's generated 59-audio example demonstrates permitted edits.

**Do not use this example hash or geometry for your own WAV.** They describe the exact bundled file above. Each real version's report must match that version's actual bytes and geometry. If the revised WAV changes, an old hash copied into the new report is invalid. There is no metadata-generation command in this CLI.

## Required audio-report fields

The top level is an object with a nonempty `segments` array. Each segment has:

| Field | Meaning and constraint |
|---|---|
| `id` | Unique JSON integer, not boolean; numeric identity used by captions |
| `file_id` | Unique nonempty stable text ID, e.g. `U001`; no NUL or `*?[]`; must align across versions |
| `path` | Canonical relative path from that version, e.g. `audio/U001.wav`; must resolve to an existing WAV within it |
| `frames` | Integer PCM frame count, verified against the WAV; in stereo one frame contains both channels |
| `sample_rate` | Integer samples per second, verified against the WAV; one common rate throughout |
| `channels` | Integer 1 or 2, verified against the WAV |
| `wav_sha256` | SHA-256 of the entire actual WAV file, including its container |
| `timeline_start_seconds` | Nonnegative JSON number on the common sample grid |
| `timeline_end_seconds` | Start plus `frames / sample_rate`; same grid |

Segments must be in timeline order without overlap. Gaps are allowed and checked during comparison. Resolved paths must be unique. The parser additionally validates supported PCM geometry; see [comparison contract](COMPARISON-CONTRACT.md).

## Required caption fields

The top level is a nonempty array. Each page has:

| Field | Meaning and constraint |
|---|---|
| `id` | Integer matching an audio segment's numeric `id` |
| `page` | Positive integer starting at 1 and consecutive within that audio item |
| `text` | Nonempty valid UTF-8 displayed text without NUL |
| `start_seconds`, `end_seconds` | Local times within the audio item; end is later than start and no later than the audio duration |
| `timeline_start_seconds`, `timeline_end_seconds` | Audio's global start plus the corresponding local time |

All times are JSON numbers on the sample grid. Pages must be globally ordered and non-overlapping. Every audio item needs at least one caption page. Across the two versions, the audio IDs/order and caption identities/count/order must stay aligned. Displayed text changes cause FAIL; identity/count/order changes cause INCONCLUSIVE.

## Policy fields

Exactly these five keys are accepted:

| Field | Allowed value |
|---|---|
| `version` | Integer `2` |
| `allow_audio_content_ids` | List of exact known audio `file_id` values allowed to change content |
| `allow_audio_duration_ids` | List allowed to change frame count; must be a subset of content IDs |
| `allow_caption_retime_ids` | Independent list allowed to change local caption boundaries |
| `audio_equality` | `bytes` or `pcm` |

Lists must contain unique IDs without wildcards. Empty lists permit no changes in that category. For an approved content-only change to U001, set only `allow_audio_content_ids` to `["U001"]`. Duration and retiming still remain protected. No policy permits changed displayed text or added/deleted pages under this contract.

Fix these permissions from the intended edit **before** comparing results. A policy written from whatever differences happened to appear cannot establish that those edits were authorized.

## Additional fields and invalid inputs

Audio and caption objects may contain extra fields, but those fields are **not inspected**. Duplicate JSON keys are rejected. JSON booleans are not numbers for IDs, geometry or timestamps. The CLI does not verify the truth of the chosen baseline, approval history, pronunciation, font/layout, SRT, MP4 or unlisted assets.

Keep all inputs stationary and use trusted copies. Absolute production paths need a provenance-preserving relocation process outside this CLI; do not silently alter original evidence to make a report pass.
