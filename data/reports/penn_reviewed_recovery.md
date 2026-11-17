# Penn source recovery after disagreement review

Five official Penn box scores from 2006–2010 were downloaded through Fetcher, with
configured robots/delay/cache behavior. Raw response hashes and robots provenance
are in `data/manifest/recovered/penn_reviewed_boxscores.csv`; raw bodies stay ignored.

| Date | Away | Home | Final |
|---|---|---|---|
| 2006-11-04 | Penn | Princeton | 30–31, 2OT |
| 2007-11-17 | Cornell | Penn | 9–45 |
| 2008-11-07 | Penn | Princeton | 14–9 |
| 2010-09-25 | Penn | Villanova | 10–22 |
| 2010-11-06 | Penn | Princeton | 52–10 |

The overlapping 2007 Cornell–Penn game merges with Cornell's copy, adding one source
rather than another game. The global snapshot remains 1,355 games / 2,710 team rows,
now with statistics for 37 games. Penn–Princeton 2006 retains num_ot=2; its aggregate
OT column is a lower bound and does not falsely contradict the explicit period count.
Incompatible explicit source values remain reported.

Validation reports 0 errors and 61 warnings. Raw source disagreements remain, with
selected fields/evidence in source_review.csv. Issue #9 stays open for the remaining
box-score coverage and Yale's unresolved 2004 games.
