# Integrated score snapshot: 2000–2026

1,355 unique games and 2,710 team rows across 26 seasons, excluding 2020. The shared
build combines the original PR #13's saved row exports with verified cached schedules
and recovered box scores. There are 756 games with box-score statistics and 599
score-only entries. Eight canceled 2001 games and four future 2026 games have no final
score and do not update pre-game records. Other played games have known final scores.

The default split configuration assigns 1,196 games to train, 107 to test and 52 to
current. All 107 test-season games have box-score statistics from the official
Ivy League source; the league copies add 94 previously score-only games.
All records are recomputed from completed games on strictly earlier dates.
Non-Ivy opponents' record fields are blank: their complete schedules are not
collected, so their true pre-game season records are unknown.

The shared schema includes stadium/city/turnovers, and neutral-site `is_home` follows
the designated home team while `neutral_site` remains a separate flag. Only parsed
pages appear in source_urls; unfetched box-score links are separate discovery data.
`data/manifest/score_sources.csv` hashes the saved exports and per-page JSON payloads;
`data/manifest/urls.csv` and recovered manifests hash actual raw responses.

`python -m ivydata build` rebuilds deterministically without network access, including
the saved exports. Full rebuilding requires matching local raw cache bodies for
verified sources; successful missing/corrupt entries stop publication. `python -m
ivydata validate` writes the current report. No wall-clock date determines output.

Source disagreements and the one reviewed date correction remain in the report;
zero structural errors do not certify every source claim as independently verified.
The main remaining work is resolving those disagreements and expanding box-score
coverage. New collection targets 2006 onward; the older Yale 2004 gaps are
deferred while already collected history is retained.
