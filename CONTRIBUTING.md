# Contributing

Contributions should preserve this tool's narrow comparison contract. The project is available under the [MIT License](LICENSE).

## Report a concrete problem

State the expected PASS, FAIL or INCONCLUSIVE result, actual result, source revision, Python version and operating system. Reproduce the smallest case with short synthetic tones and invented captions. Do not post production speech, customer captions, personal paths, account identifiers, credentials or private archives.

Keep audio-content permission, duration permission and caption-local-retiming permission separate. For a timing change, cover both the intended result and a one-sample unintended change. Do not widen timing tolerances or permissions merely to make a case pass.

## Verify a change

Use Python 3.12 in a writable working directory with a writable temporary directory:

```sh
python -m unittest -v
```

No third-party Python packages are required. Preserve failures and skips in the record. The GitHub Actions workflow explicitly selects Python 3.12; it has a manual trigger and read-only repository permission. A local run does not establish remote CI success.

## Keep the contract narrow

New formats require a clear schema and evidence of need. Automatic media editing, pronunciation approval, semantic correctness and finished-video QA are outside this tool's current purpose. A checksum script can implement similar logic; explain a concrete defect or user need rather than claiming novelty.

Only contribute material you have the right to share under the project's license.
