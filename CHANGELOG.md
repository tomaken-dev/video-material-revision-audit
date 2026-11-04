# Changelog

## 0.3 source update on 2026-11-03 UTC

- Apply the MIT License, copyright 2026 tomaken-dev.
- Explicitly select Python 3.12 in GitHub Actions. Keep a manual trigger and read-only repository permission; add no automatic or scheduled runs.
- Ignore generated report filenames shown in the documentation.
- Replace private preparation text with public-facing usage, contribution and validation documentation.
- Verify the source on Linux CPython 3.12.14: 47 tests passed without skips. Execute the README commands, exact one-item input example, unauthorized-audio FAIL, missing-WAV INCONCLUSIVE and output-collision checks with input preservation.
- Keep application logic, fixture generation, test expectations and synthetic media unchanged. No audit-logic fix was required by this verification.
- Distinguish current Linux verification, historical Windows checks and unexecuted remote CI.

See [validation](VALIDATION.md) for evidence and limitations.

## Documentation update on 2026-11-02 JST

- Organize English and Japanese READMEs around the workflow, first run and result interpretation.
- Document exact input fields and a complete one-item synthetic example.
- Explain per-ID permissions, exact sample timing and bytes versus PCM equality.

## Earlier 0.3 implementation

- Use exact integer sample coordinates for permitted duration changes and subsequent timeline shifts.
- Separate audio content, duration and caption-local-retiming permissions.
- Stream WAV hashes and validate ordinary PCM geometry and RIFF structure.
- Reject unsupported or invalid input as INCONCLUSIVE; create reports without overwriting existing files.
- Use ASCII-safe stdout JSON and UTF-8 report files; explicitly read UTF-8 JSON in test helpers.
- Include synthetic regressions for malformed inputs, permissions, timing precision and output protection.

The application report version remains `0.3-candidate`; the permission-policy version remains 2.
