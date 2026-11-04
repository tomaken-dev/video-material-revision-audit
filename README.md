# Video Material Revision Audit

Detect unintended changes after a targeted audio revision: protect unchanged WAV files and caption text, and check that downstream timing follows only the duration changes you permitted.

Python 3.12 standard library only. Runs locally without an account, network connection or paid API. Released under the [MIT License](LICENSE).

[日本語](README.ja.md) · [Input format](INPUT-FORMAT.md) · [Exact comparison contract](COMPARISON-CONTRACT.md) · [Validation](VALIDATION.md)

## Is this for your workflow?

Use it when you keep two versions of one ordered PCM audio timeline, stable audio IDs, and caption JSON in the documented format. It is useful for a narrow revision such as replacing two utterances while protecting everything else.

It is **not** an importer for arbitrary WAV folders, SRT or MP4. Caption text rewrites, page additions/removals and reordered material require a different comparison contract. A PASS does not approve pronunciation, speech/subtitle synchronization, slide layout or the finished video.

## Try the included example

From this directory, with Python 3.12 available as `python`, run:

```sh
python fixtures.py synthetic_demo_new
python audit.py synthetic_demo_new/修正前 synthetic_demo_new/修正後 synthetic_demo_new/policy.json --output new_result.json
python -m unittest -v
```

Use a fresh destination and output filename; the generator refuses an existing destination and the audit never overwrites an existing output file. If your Python 3.12 command is `python3`, use that consistently instead. These commands need a writable working directory and temporary directory.

The example contains synthetic tones, not real speech. Its expected audit result is PASS: 59 audio items, 57 unchanged, 114 unchanged caption texts, and 222 samples of permitted total duration change. The test suite is a separate check, not part of those counts. Recorded Linux and Windows results and their limitations are in [validation](VALIDATION.md).

## Audit your own revision

1. Choose the last approved baseline and the revised version; keep both as stationary copies in separate directories.
2. Supply `audio/audio_report.json`, `audio/caption_timeline.json`, and referenced PCM WAVs in each version. Follow the [one-item example and field rules](INPUT-FORMAT.md); renaming an unrelated JSON file does not convert it.
3. Before inspecting the differences, list the exact audio IDs allowed to change in a separate policy. Content changes, duration changes and local caption retiming have separate permissions.
4. Run `python audit.py before after policy.json --output result.json`, choosing a new output path.
5. Read `status`, `violations` and `unknowns`. When present, inspect `effective_policy`, `audio_equality` and the per-item results as well. Do not expand permissions just to clear an unexpected violation.

| Result | Exit code | Next action |
|---|---:|---|
| PASS | 0 | No violation was found within the inspected contract. Separately review the allowed edits and finished output. |
| FAIL | 1 | Inspect the reported violations and correct unintended edits. |
| INCONCLUSIVE | 2 | Resolve missing, invalid or unsupported inputs, or output-save failure. Any already-reported violations still matter. |

## What this adds to a simple checksum comparison

A checksum can say that a file changed. This tool additionally checks the change against a predeclared per-ID policy and relates permitted duration changes to subsequent audio and caption timing. It verifies report metadata against actual WAV bytes and does not treat unsupported input as a pass. See the [code-backed comparison](COMPARISON-CONTRACT.md#comparison-with-a-simple-checksum-list).

This describes implemented behavior, not a benchmark or a claim of superiority over other audit tools. External adoption and end-to-end time savings have not been measured.

## Boundaries and evidence

- Only ordinary integer PCM WAV and the documented JSON fields are inspected. Mixed sample rates and WAVE_FORMAT_EXTENSIBLE are unsupported.
- Caption text and page identities must stay fixed across the two versions. Font, style, additional JSON fields, SRT and MP4 are not checked.
- Trusted, stationary material copies are required. This is not a hostile-file sandbox or a check of whether the baseline itself is correct.
- Complete production-revision acceptance, external adoption and time savings have not been demonstrated. Synthetic results do not establish those outcomes.
- Current Linux verification and historical Windows results are recorded separately. A Windows symlink test skipped for insufficient privilege is not verified by a Linux success. [Evidence and limitations](VALIDATION.md) · [Changes](CHANGELOG.md)

[Contributing](CONTRIBUTING.md) describes the contribution scope and safe reproduction requirements. The GitHub Actions workflow explicitly selects Python 3.12 and runs only when manually requested. Local test results are not a claim that remote CI has passed.
