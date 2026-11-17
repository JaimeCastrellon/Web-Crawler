# Brown recovery: 2004 and 2025

This records the bounded PR #25 recovery stage; the current combined dataset also
includes the separately reviewed historical score exports.

Fetched through the configured robots-aware Fetcher, with its per-host delay and
cache reuse. Provenance for two schedules, twenty box scores and robots.txt is in
`data/manifest/recovered/brown_2004_2025.csv`. Raw responses remain uncommitted.

All twenty boxes returned HTTP 200, match schedule date/teams/finals, contain every
team-stat field, and parse without warnings. Brown's modern table keeps Brown last
even in away games; explicit home/visiting team names in the saved JSON state fix
orientation. The 2025 `(RV)` and `#8/10` decorations are removed from team ids.

| School | Season | Games | Box scores | Coverage |
|---|---:|---:|---:|---|
| Brown | 2004 | 10 | 10 | full |
| Brown | 2025 | 10 | 10 | full |
| Yale | 2004 | 10 | 6 | partial |

Combined output: 29 games, 58 team rows, 25 games with team statistics, four score-only.
The overlapping Brown–Yale 2004 game is merged. Build and coverage reruns are
byte-identical. Validation reports 0 errors and 22 known source/coverage warnings.

Issue #9 stays open. The unresolved Yale 2004 boxes are Dayton, Colgate, Lehigh and
Princeton; the wider historical source audit is still pending. Saved Lehigh/Princeton
archives were rechecked but did not supply a new standalone full box score. The
larger score-dataset proposal in PR #13 is separate and still needs integration review.
