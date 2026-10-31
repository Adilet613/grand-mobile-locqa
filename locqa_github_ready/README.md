# locqa · portable CLI source

This directory is the GitHub-ready source component. It contains no official
Grand Mobile input data, corrected production strings or production report.
The rest of the submission archive is private and must not be published.

Python 3.10+; runtime uses the standard library. Install and run:

```bash
python -m pip install .
locqa check --source intl_ru.arb --target intl_kk.arb --glossary glossary.csv --out report.json
```

Check emits official-schema issue candidates, standalone report.html and a
summary sidecar. Runtime checks are deterministic and offline. Severity/confidence
are rule assessments, not calibrated probabilities. The stored final 145-finding
report was additionally adjudicated by AI and does not equal the raw candidates.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Pytest collects the unittest regression suite and the dedicated parameterized
plural, placeholder and suffix tests. Fixtures are synthetic. All eleven official
issue codes are supported; linguistic heuristics are conservative baselines and
do not constitute complete natural-language understanding.

Use --config for allow_identical, allowed_blank_keys, max_chars, runtime_suffix_keys
and locale. Use --use-escaping only when Flutter l10n.yaml enables that mode.
The parser supports broader ICU constructs than Flutter; actual gen-l10n is the
compiler gate. Duplicate ARB keys use the last occurrence and are reported in the
summary. Inputs are never overwritten by outputs.

`locqa apply` accepts a manifest with explicit human confirmation, reviewer,
timestamp and matching source/target hashes. It refuses stale or unsafe changes.
Do not fabricate review attestations. Optional `locqa propose` sends selected rows
to an explicitly configured model API and only writes unreviewed suggestions.
See `python -m locqa --help` and each subcommand's --help for options.

The optional model adapter was tested with mocks; no provider/model identity is
assumed. Do not put API credentials or partner data into a public repository.
