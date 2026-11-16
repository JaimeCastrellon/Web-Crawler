# Test fixtures

Saved HTML pages that parser tests run against, so tests never hit the network.

To (re)capture them, from the repo root on a machine with internet access:

```bash
python -m ivydata fixtures
git add tests/fixtures/*.html && git commit -m "Add HTML fixtures"
```

The URL list is `fixtures.yaml`. Keep fixtures few and small — add one only when a parser
needs a new page shape (e.g. an overtime game, an old-format season, a neutral site).
