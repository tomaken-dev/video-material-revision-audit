# Validation evidence and limits

## Current Linux verification on 2026-11-03 UTC

Linux CPython 3.12.14 ran the full standard-library suite from the source root: **47 tests passed, no failures and no skips**. Command: `python3 -m unittest -v`. Unittest reported 1.290 seconds.

Additional CLI checks used a fresh source copy and synthetic inputs:

| Check | Expected and observed result | Preservation |
|---|---|---|
| README fixture generation and audit | PASS, exit 0; 59 audio, 57 unchanged, 114 unchanged caption texts, permitted delta 222 samples | All 123 inputs unchanged |
| Unauthorized PCM byte change with correctly updated report hash | FAIL, exit 1; U003 unapproved audio change | All 123 inputs unchanged |
| Missing referenced WAV | INCONCLUSIVE, exit 2 | All 122 remaining inputs unchanged |
| Existing output file | INCONCLUSIVE, exit 2; fallback JSON on stdout | All 123 inputs and existing report unchanged |
| INPUT-FORMAT one-item JSON copied verbatim | PASS, exit 0; one unchanged audio and caption, zero delta | All seven inputs unchanged |

The [machine-readable verification record](validation/20261103-linux.json) records the outcomes and SHA-256 values of the exact application, generator and test files. These are synthetic contract checks, not production-project acceptance.

No audit-logic or test-expectation change was required by these checks. The release-facing changes apply MIT licensing, select Python 3.12 in the manual CI workflow, ignore documented generated reports and update documentation.

## Historical Windows evidence

The recorded 2026-11-01 Windows 11 / CPython 3.12.10 run used CP932 with UTF-8 mode off: 46 tests passed and one symlink-loop test was skipped because the account lacked symlink-creation privilege. The application, generator and tests remain byte-identical to those verified files.

This Windows run is historical. Windows was not rerun in the Linux verification above. Linux success does not establish the skipped Windows condition. Earlier private handoff and execution archives are not bundled with this source.

## Reproduce

Use Python 3.12 and writable working and temporary directories. From the source root:

```sh
python -m unittest -v
python fixtures.py synthetic_demo_new
python audit.py synthetic_demo_new/修正前 synthetic_demo_new/修正後 synthetic_demo_new/policy.json --output new_result.json
```

Use fresh fixture and output names. If your executable is `python3`, use it consistently. Record the actual date, OS, Python version, source revision, status, exit code and skipped-test reasons.

GitHub Actions explicitly selects Python 3.12 and has a manual trigger. **Remote CI was not executed in this local verification.** A workflow file is not evidence of a successful workflow run.

## Limits

These checks do not establish full production-revision acceptance, final-video quality, pronunciation, speech alignment, layout, external adoption, time savings, comparative superiority or ecosystem importance. Arbitrary exports, SRT, MP4, mixed rates and WAVE_FORMAT_EXTENSIBLE remain unsupported. Hostile resource exhaustion and concurrent file changes are outside the guarantee.

A passing synthetic example demonstrates the stated [comparison contract](COMPARISON-CONTRACT.md) only.
