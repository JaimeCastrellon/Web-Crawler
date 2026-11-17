# Expanded Ivy League conference box-score recovery

Collection scope agreed 2026-11-17: retain previously collected older rows; new
requests target 2006–2026, newest first. The initial 37 detailed-stat games rose
to 131 after the first 2024–2025 recovery. This expansion brings the total to
596 detailed-stat games, still 1,355 games / 2,710 team rows.

## Accepted league pages

574 official league box scores are checksum-verified in the recovery manifest.
They include all 107 test-season games and all known completed games for 2017–2026
(excluding 2020). Earlier modern indexes are partial: 2012–2016 expose ten Penn
games each, and 2009–2011 expose nineteen distinct Brown/Penn games each.
2006–2008 indexes have no football box-score links; those limitations remain
explicit in the recovery-error and validation reports.

The expanded snapshot adds 465 detailed-stat games relative to the initial
131-game state of this PR. Previously collected non-league boxes remain intact.
All 5,136 team-stat cells for the 2024–2025 test seasons are populated. Missing
values elsewhere remain missing, and four upcoming 2026 games keep blank results.

All HTTP used Fetcher with the configured User-Agent, robots permission and the
league's five-second Crawl-delay. Cache hits were reused without refresh. The
season order is newest first. Index leaders and cumulative totals are discovery
context only; printed W-L records never enter features. League mirrors are not
independent statistical measurements of the school-hosted copy. Raw pages remain
ignored; only small curated fixtures and factual output/provenance are committed.

## Review findings

- Verified abbreviations/mascot names preserve canonical identities, including
  Morgan St., URI, CCSU, USD, Princeton Tigers and Penn Quakers.
- The league's 2018 San Diego–Harvard box has a one-day date error. A cached
  official Harvard schedule proves September 15 with the same teams and 36–14
  final. The bounded, checksum-checked review retains the raw date disagreement.
- Four additional field reviews correct Brown's 2009 Stony Brook visit, Penn's
  2011 Villanova visit, Brown's 34 points vs Holy Cross in 2009, and Brown's
  21 points at Columbia in 2011. The field ledger records source hashes/times.
- Neutral-game designated home teams now follow the official boxes. Team-aligned
  points remain unchanged for those orientation updates.
- Three signed sack-yard totals are negative and their play descriptions report
  gains. Signed values are preserved. Validation now correctly applies the
  project's negative-yardage allowance to sack_yds_lost as well.

Validation: 0 errors, 75 warnings. There are 29 source-disagreement flags, all
covered by the review ledger; reviews do not erase contrary claims. The ledger
now covers 32 fields across 31 games, including the two OT-only cases.
316 offline tests pass; normal format/lint/duplicate checks and rebuild
determinism are checked before publication. No output columns changed.

`python -m ivydata league-boxscores --seasons 2006-2026` is resumable. Offline
`build`, `coverage`, and `validate` reuse the local cache. Early school-source
recoveries are being published separately. Earlier 2000–2005 gaps are deferred.
