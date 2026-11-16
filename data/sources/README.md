# Source exports (inputs to the build)

Extracted schedule rows — not raw HTML — saved by the scripts in `tools/browser/` on
2026-11-16. Rebuild everything in `data/processed/` and `data/reports/` with:

```bash
python -m ivydata scores \
  --official data/sources/ivy_official_cornell.json data/sources/ivy_official_penn.json \
             data/sources/ivy_official_yale.json \
  --wikipedia data/sources/ivy_wikipedia_schedules.json
```

| file | source | coverage |
|---|---|---|
| `ivy_official_yale.json` | yalebulldogs.com schedule pages | 2000–2026 |
| `ivy_official_cornell.json` | cornellbigred.com schedule pages | 2000–2026 |
| `ivy_official_penn.json` | pennathletics.com schedule pages | 2000–2026 |
| `ivy_wikipedia_schedules.json` | Wikipedia team-season articles, all 8 schools (CC BY-SA 4.0) | 2000–2026 |

Harvard, Brown, Columbia, Dartmouth and Princeton's sites returned bot challenges to the
browser crawl (see `docs/SOURCES.md`), so their games against each other come from
Wikipedia only in this build.
