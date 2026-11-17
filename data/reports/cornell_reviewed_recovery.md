# Cornell source recovery after disagreement review

Five official Cornell box scores from 2002, 2007 and 2009 were downloaded through
Fetcher, with configured robots/delay/cache behavior. Provenance (including robots)
is in `data/manifest/recovered/cornell_reviewed_boxscores.csv`; raw pages stay ignored.

| Date | Away | Home | Final | Notable review |
|---|---|---|---|---|
| 2002-10-26 | Cornell | Brown | 10–7 | two OT sessions; table combines OT points |
| 2007-09-22 | Cornell | Yale | 12–51 | Yale is home |
| 2007-11-17 | Cornell | Penn | 9–45 | Penn is home |
| 2009-10-31 | Cornell | Princeton | 13–17 | confirms selected Cornell points |
| 2009-11-07 | Cornell | Dartmouth | 17–20 | explicit second-OT play note |

The global snapshot remains 1,355 games / 2,710 team rows, with box-score stats for
33 games. Both OT games retain num_ot=2. The 2002 box table alone does not establish
the period count; Cornell's official history and explicit schedule label establish
two sessions. Raw source discrepancies are retained in validation and the review ledger.
Issue #9 stays open for other sources and remaining gaps.
