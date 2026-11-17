# Collection scope and handoff: 2006 onward

Recovery snapshot and user decision on 2026-11-17: keep previously collected older rows; new collection
starts in 2006, newest seasons first. Configured split ranges stay unchanged.
The 312 existing 2000–2005 game identities, dates, final scores, home/neutral
designations and full/score-only levels are unchanged from the initial league PR.
After this scope decision, no new requests were made for those earlier gaps.

## Current dataset

- 1,355 unique games / 2,710 team rows retained.
- 698 games have parsed box-score statistics overall, up from 131
  before this scope decision.
- Active 2006–2026 scope: 1,043 game rows, 1,039 completed games,
  682 with box-score statistics (65.6% of completed games).
- 357 completed active-scope games remain score-only; four upcoming
  2026 games keep blank results. 2020 is excluded.
- Every known completed game from 2017 onward has box-score statistics.
  The 2024–2025 test split has all 107 games covered.

The official league source supplies 574 accepted pages; the older 2009–2016 indexes
are partial, and 2006–2008 indexes expose no box-score links. School recovery then
adds 102 detailed-stat games from six usable sources. Matching copies are
provenance corroboration, not independent statistical measurements.

| Early source | Verified box pages | Newly detailed games at that stage |
|---|---:|---:|
| [Brown](recovery/brown_2006_2008.md) | 24 | 24 |
| [Columbia](recovery/columbia_2006_2008.md) | 18 | 17 |
| [Cornell](recovery/cornell_2006_2008.md) | 28 | 23 |
| [Dartmouth](recovery/dartmouth_2006_2008.md) | 13 | 11 |
| [Harvard](recovery/harvard_2006_2008.md) | 0 | 0 |
| [Penn](recovery/penn_2006_2008.md) | 30 | 20 |
| [Princeton](recovery/princeton_2006_2008.md) | 10 | 7 |
| [Yale](recovery/yale_2006_2008.md) | 0 | 0 |

The Harvard and Yale reports document unsuccessful public archive probes, without
inventing games/statistics. Their matchups may be covered by opponent copies.
Every source has an attempt inventory and URL-bearing failure/deferred report.
All school HTTP used Fetcher, configured identity, robots rules and delays; raw
responses remain local and ignored. No printed W-L records are model features.

## Completed-game coverage by period

| Period | Completed games | With box stats | Still score-only |
|---|---:|---:|---:|
| 2017–2026 | 467 | 467 | 0 |
| 2009–2016 | 416 | 109 | 307 |
| 2006–2008 | 156 | 106 | 50 |

[Per-season counts](collection_2006_onward.csv).

## Remaining work

Fill the 357 completed-game gaps, concentrated in 2006–2016. Prioritize other
official school copies and then supported public archives. Harvard/Yale early
archive access and incomplete old league indexes remain limitations. Previously
tracked 2000–2005 gaps, including Yale 2004, are deferred rather than pursued.
Issue #9 stays open. Issue #8's validation implementation remains awaiting merge.

All 32 raw source-disagreement flags remain visible and have field-ledger coverage.
Three explicit one-day date reviews require checksum/metadata-verified official
schedules with matching teams/finals. Signed net sack-yard values are retained
from source descriptions. Unknown values stay missing rather than becoming zero.

Review the dependency stack before merging: existing #21–#25, then #13, #26–#28,
then the source-specific PRs #29–#36. Nothing was merged into main in this run.

Final verification: 330 offline tests pass. Validation reports 0 errors and 176
warnings covering source access/parse limitations and retained disagreements.
Quality checks and byte-identical rebuild verification accompany publication.
