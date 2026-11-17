# Collection progress: 2006 onward

Snapshot on 2026-11-17. New collection starts in 2006, newest seasons first.
Previously collected older rows and configured split ranges stay intact. The 312
existing 2000–2005 game identities, dates, final scores, home/neutral designations
and full/score-only levels are unchanged from the initial league PR. No new
requests after the scope decision target those earlier gaps.

## Current dataset

- 1,355 unique games / 2,710 team rows retained.
- 749 games have box-score statistics overall, up from 131 before the
  league and school recovery work.
- Active 2006–2026 scope: 1,043 game rows, 1,039 completed games;
  733 have box-score statistics (70.5% of completed games).
- 306 completed active-scope games remain score-only. Four upcoming 2026
  games keep blank results. 2020 is excluded.
- Every known completed game from 2017 onward has box-score statistics.
  All 107 games in the 2024–2025 test split have box-score statistics.

A parsed box score can still have missing fields: `full` does not guarantee
that every statistic column is populated. Matching school/league copies provide
corroboration and additional fields rather than duplicate statistical observations.

## Recovery sources

The league supplies 574 accepted box-score pages. Its 2009–2016 indexes are partial;
2006–2008 indexes expose no box-score links. The following early school work added
102 distinct detailed-stat games after the league pass.

| 2006–2008 source | Verified box pages | Newly detailed games at that stage |
|---|---:|---:|
| [Brown](recovery/brown_2006_2008.md) | 24 | 24 |
| [Columbia](recovery/columbia_2006_2008.md) | 18 | 17 |
| [Cornell](recovery/cornell_2006_2008.md) | 28 | 23 |
| [Dartmouth](recovery/dartmouth_2006_2008.md) | 13 | 11 |
| [Harvard](recovery/harvard_2006_2008.md) | 0 | 0 |
| [Penn](recovery/penn_2006_2008.md) | 30 | 20 |
| [Princeton](recovery/princeton_2006_2008.md) | 10 | 7 |
| [Yale](recovery/yale_2006_2008.md) | 0 | 0 |

The next pass targets 2014–2016. Each source report records the dataset count at
its own stage; newly detailed games are incremental in dependency order.

| 2014–2016 source | Verified box pages | Newly detailed games at that stage |
|---|---:|---:|
| [Brown](recovery/brown_2014_2016.md) | 27 | 27 |
| [Cornell](recovery/cornell_2014_2016.md) | 24 | 24 |

Every source has a request inventory and URL-bearing failure/deferred report.
Blocked or unsupported pages remain gaps. All requests use Fetcher, the configured
identity, robots rules and per-host delays. Raw responses remain local and ignored.
Printed W-L records are never model features.

## Completed-game coverage by period

| Period | Completed games | With box stats | Still score-only |
|---|---:|---:|---:|
| 2017–2026 | 467 | 467 | 0 |
| 2014–2016 | 156 | 81 | 75 |
| 2009–2013 | 260 | 79 | 181 |
| 2006–2008 | 156 | 106 | 50 |

[Per-season counts](collection_2006_onward.csv).

## Remaining work

306 completed-game gaps remain in the active scope. Continue with official
opponent copies and supported public archives, newest seasons first. Access
restrictions and incomplete old league indexes remain limitations. Existing
2000–2005 rows are retained; their gaps, including Yale 2004, stay deferred.
Issue #9 remains open. Issue #8's validation implementation awaits merge.

All 32 raw source-disagreement flags remain visible and have field-ledger
coverage. The 3 explicit one-day date reviews require checksum/metadata-
verified official schedules with matching teams and finals. Unknown values
stay missing. Signed net sack-yard values remain as reported by the source.

Review the dependency stack before merging: #21–#25, #13, #26–#28, #29–#36,
then the 2014–2016 source PRs. Nothing is merged automatically.

Verification: 337 offline tests pass. Validation reports 0 errors and
176 warnings, including access/parse limitations and retained disagreements.
Lint, formatting, duplicate-id and whitespace checks accompany publication.
