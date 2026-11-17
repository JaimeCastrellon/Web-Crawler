# Ivy League conference box-score recovery

Checked 2026-11-17 after the initial 37-game collection. The conference source had
not previously been integrated. Its populated season indexes are:

- https://ivyleague.com/stats.aspx?path=football&year=2024 — 52 distinct game links.
- https://ivyleague.com/stats.aspx?path=football&year=2025 — 55 distinct game links.

All 107 game pages were captured through Fetcher with the configured User-Agent,
robots permission, the league's five-second delay and checksum-verified caching.
An initial transport disconnect completed on a subsequent uncached retry. Populated
conference tables also required a page-shape correction: these boxes omit the
school-site wrapper and include monitoring scripts. Script-only challenges remain
rejected. All index and accepted box hashes/timestamps, plus robots provenance, are
in `data/manifest/recovered/ivy_league_boxscores.csv`. Raw HTML stays ignored.

## Dataset result

- Still 1,355 unique games and 2,710 team rows. No new duplicate games.
- Detailed-stat games rise from 37 to 131, adding 94 games; 13 already had school copies.
- All 52 games in 2024 and all 55 in 2025 now have team box-score statistics.
- All 5,136 team-stat cells in those two seasons are populated; missing values
  elsewhere remain missing. No cumulative season totals or printed W-L records are used.
- Existing dates, team identities, final scores, home/neutral designations, split
  labels and pre-game record columns are unchanged. The 24 disputed-game flags remain.
- Four verified abbreviations (UAlbany, Central Conn. St., Youngstown St., Montana St.)
  map to existing canonical opponents instead of introducing duplicate games.
- League pages mirror official game reports, so matching copies are provenance
  corroboration rather than independent measurements.

`python -m ivydata league-boxscores --seasons 2024,2025` resumes from the cache;
`build`, `coverage`, and `validate` remain offline. Recovery errors are retained in
`league_recovery_errors.csv` and included by the build in validation warnings.
After the successful recovery that file contains only its header.

## Checks and remaining work

300 offline tests pass, including actual league fixtures, two-overtime scoring,
strict season/sport/host link selection, failure persistence/resume, validation
reporting, interruption/resume, canonical aliases and one-to-one provenance for all 107 games.
Validation reports 0 errors and 61 warnings. All 14 generated CSV/report outputs remain byte-identical after repeated offline
build, coverage and validation. Format/lint/duplicate checks pass.

The modern season selector advertises 2009–2026 (no 2020); older advertised seasons
remain to be collected. A populated 2008 summary exists on static.ivyleague.com,
but the analogous 2004 path returns a 68-byte not-found body despite HTTP 200.
The two probe hashes/timestamps are in `league_archive_probe.csv`; neither summary
is imported into model data. Yale's 2004 Dayton/Colgate/Lehigh/Princeton gaps remain.
Issue #9 stays open for broader train/current collection and remaining source review.
