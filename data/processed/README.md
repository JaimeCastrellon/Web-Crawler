# First processed snapshot: Yale 2004 only

10 games and 20 team rows, built offline from the committed main URL manifest plus
all six recovered-source manifests. Six games have team statistics; Dayton, Colgate,
Lehigh and Princeton remain score-only. This is not the full historical dataset.

All rows are train data under the current split configuration. Test/current files
are intentionally header-only. Source URLs are retained per game. Pre-game records
count only completed games observed on earlier dates in this dataset; Yale's ten-game
schedule is present, but opponents' full schedules are not. Do not interpret those
opponents' records as complete season records.

`python -m ivydata build` regenerates this snapshot from the matching local raw cache
(no network). Cache bodies are ignored by Git; the manifests preserve their checksums.
A fresh download requires updated provenance if the response body changes. Known
failed original Yale links are listed in `data/reports/build_warnings.csv`; the six
working alternate box scores are included despite those original-link failures.
The full validation report remains task 8. No data from the separate score-dataset
PR is included in this snapshot.
