# Comparison contract / 比較の仕様

This describes `audit.py` as shipped in the 0.3 candidate. It is not a new feature or a claim of project acceptance.

## Comparison with a simple checksum list

Here “simple checksum list” means recording and comparing whole-file SHA-256 values only, without additional policy or timeline logic. It does not represent every existing audit product.

| Question | Simple checksum list | This CLI |
|---|---|---|
| Did WAV bytes change? | Yes | Yes in `bytes` mode; `pcm` mode instead compares PCM samples and geometry |
| Was that audio ID permitted to change? | No built-in policy | Exact per-ID content permissions |
| Was the duration change allowed? | Cannot interpret duration | Separate duration permission; must also allow content |
| Did later audio shift by exactly the permitted accumulated duration delta? | Cannot interpret timing | Exact sample-coordinate check; existing gaps preserved |
| Did displayed caption text change? | Can detect changed JSON bytes, not the selected field's meaning | Per-page displayed text checked; changes are violations |
| Was local caption retiming separately permitted? | No built-in policy | Independent per-audio-ID permission, with bounds and ordering checks |
| Do report hash, rate, frame count and channel count match the WAV? | Depends on a separate verifier | Checked while loading each version |
| Does PASS approve speech quality, layout or the final video? | No | No |

Implementation evidence: `inspect_wav` validates the WAV and computes hashes; `load_project` checks file metadata and coordinates; `policy_read` validates permissions; `audit` compares the two projects. This is a description of those functions, not a performance or market comparison. A custom checksum script could implement equivalent extra logic.

## Exact time

All files in and across the two versions must use one sample rate. WAV integer frame counts are authoritative. Imported JSON decimal times must lie on the sample grid; at most 0.000001 sample of serialization roundoff is tolerated when converting them. Subsequent comparisons use integer samples exactly. An unintended one-sample shift is not rounded away.

The new start of each audio item must equal its old start plus the sum of earlier **permitted** frame-count changes. Duration permission must be a subset of content permission. Channels and sample width cannot change. Audio IDs and their order must align across versions.

## Audio equality

- `bytes`: unapproved whole WAV files must be byte-identical, including container metadata.
- `pcm`: unapproved raw PCM samples must match, with unchanged rate, channels and sample width. Container metadata may differ. This is not perceptual equality or a test that speech sounds the same.

`audio_unchanged` is interpreted using the selected mode, not always byte identity.

## Caption checks

Caption pages align by stable audio `file_id` plus page number. Their identities, count and order must match across versions; otherwise comparison is INCONCLUSIVE. Changed displayed text is a violation. Local caption times must remain unchanged unless their audio ID has explicit retiming permission. Global coordinates must always equal the corresponding audio start plus local coordinates, and pages must remain non-overlapping and within their audio.

Retiming permission does not prove that words match the speech. Additional JSON fields, typography, SRT and rendered output are not inspected.

## Permission and output boundaries

The policy contains exactly the five fields documented in [INPUT-FORMAT.md](INPUT-FORMAT.md). IDs must be exact, known and unique; no wildcards. Caption-retiming permission is independent of content permission.

`effective_policy` and `audio_equality` appear only after policy validation reaches that stage. Their absence means they were not established; do not infer empty or default permissions. A later unsupported condition can leave already-detected violations in an INCONCLUSIVE report. A failure to save a new output file also returns INCONCLUSIVE and prints the report to standard output.

## File and media boundaries

Paths must be canonical relative POSIX-style paths inside the version directory; escaping symlinks, duplicate resolved references, absolute paths, backslashes and colon-containing paths are rejected. The two versions cannot resolve to the same directory. Do not modify files while an audit runs.

Only format-tag-1 integer PCM WAV, 8/16/24/32-bit mono/stereo, is supported. A single 16-byte or empty-extension 18-byte `fmt` chunk must precede the `data` chunk and geometry must be consistent. Compressed audio, WAVE_FORMAT_EXTENSIBLE and mixed rates are unsupported. Valid unknown RIFF chunks are metadata. Bytes after the declared RIFF end participate in byte equality, not PCM equality. An omitted odd final-data pad is accepted for Python writer compatibility.

WAV hashes are streamed in chunks; JSON and the material index still use memory proportional to input size. This is not a hostile-media sandbox, a concurrent-modification guarantee, or validation of unlisted assets and baseline provenance.
