# Test fixtures

Saved HTML pages that parser tests run against, so tests never hit the network.

To (re)capture them, from the repo root on a machine with internet access:

```bash
python -m ivydata fixtures
git add tests/fixtures/*.html && git commit -m "Add HTML fixtures"
```

The URL list is `fixtures.yaml`. Keep fixtures few and small — add one only when a parser
needs a new page shape (e.g. an overtime game, an old-format season, a neutral site).

The command prints each name, HTTP status, and byte count. Missing pages, robots denials,
and network failures are reported and later entries continue; only HTTP 200 bodies are
saved. Failed captures leave existing fixtures in place. Responses (including errors) are
reused from `data/raw/`; use `python -m ivydata fixtures --refresh` to explicitly refetch.
