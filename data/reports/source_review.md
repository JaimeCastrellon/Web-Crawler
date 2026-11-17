# Source disagreement review

This ledger preserves raw source disagreement flags. It records evidence for selected values; it does not rewrite the saved exports or erase contrary claims.

The initial pass reviewed 27 disputed fields across 26 games (including two overtime-only disagreements).

`verified_cached` means the disputed fields were checked against a populated, checksum-verified official page or box score. `corroborated_exports` means at least two saved exported copies support the selected value. `needs_primary_evidence` remains open.

| Game | Field | Selected | Review | Evidence |
|---|---|---|---|---|
| 20001118-dartmouth-at-princeton | away_pts | 42 | verified_cached | https://dartmouthsports.com/sports/football/opponent-history/princeton-2017/76 |
| 20001118-penn-at-cornell | home_team | cornell | corroborated_exports | https://cornellbigred.com/sports/football/schedule/2000-01 / https://en.wikipedia.org/wiki/2000_Cornell_Big_Red_football_team / https://pennathletics.com/sports/football/schedule/2000 |
| 20010929-penn-at-dartmouth | date | 2001-09-29 | verified_cached | https://pennathletics.com/sports/football/schedule/2001 |
| 20011110-yale-at-princeton | home_pts | 34 | corroborated_exports | https://en.wikipedia.org/wiki/2001_Princeton_Tigers_football_team / https://yalebulldogs.com/sports/football/schedule/2001 |
| 20021019-columbia-at-penn | away_pts | 0 | verified_cached | https://pennathletics.com/sports/football/schedule/2002 |
| 20021026-cornell-at-brown | num_ot | 2 | verified_cached | https://cornellbigred.com/sports/football/opponent-history/brown-university/2 |
| 20031011-dartmouth-at-yale | date | 2003-10-11 | corroborated_exports | https://en.wikipedia.org/wiki/2003_Dartmouth_Big_Green_football_team / https://yalebulldogs.com/sports/football/schedule/2003 |
| 20061104-penn-at-princeton | away_pts | 30 | verified_cached | https://pennathletics.com/sports/football/stats/2006/princeton/boxscore/8129 |
| 20061104-penn-at-princeton | home_pts | 31 | verified_cached | https://pennathletics.com/sports/football/stats/2006/princeton/boxscore/8129 |
| 20070922-cornell-at-yale | home_team | yale | verified_cached | https://cornellbigred.com/sports/football/stats/2007-08/yale-university/boxscore/3522 |
| 20071117-cornell-at-penn | home_team | penn | verified_cached | https://pennathletics.com/sports/football/stats/2007/cornell/boxscore/6967 |
| 20080920-yale-at-georgetown | home_team | georgetown | verified_cached | https://yalebulldogs.com/sports/football/schedule/2008 |
| 20081004-princeton-at-columbia | home_team | columbia | verified_cached | https://goprincetontigers.com/sports/football/schedule/2008-09 |
| 20081018-brown-at-princeton | home_team | princeton | verified_cached | https://goprincetontigers.com/sports/football/schedule/2008-09 |
| 20081025-harvard-at-princeton | home_team | princeton | verified_cached | https://goprincetontigers.com/sports/football/schedule/2008-09 |
| 20081107-penn-at-princeton | home_team | princeton | verified_cached | https://pennathletics.com/sports/football/stats/2008/princeton/boxscore/8815 |
| 20081115-princeton-at-yale | home_team | yale | corroborated_exports | https://en.wikipedia.org/wiki/2008_Yale_Bulldogs_football_team / https://yalebulldogs.com/sports/football/schedule/2008 |
| 20091031-cornell-at-princeton | away_pts | 13 | verified_cached | https://cornellbigred.com/sports/football/stats/2009-10/princeton-university/boxscore/8093 |
| 20091107-cornell-at-dartmouth | num_ot | 2 | verified_cached | https://cornellbigred.com/sports/football/stats/2009-10/dartmouth-college/boxscore/8094 |
| 20091114-yale-at-princeton | away_pts | 17 | corroborated_exports | https://en.wikipedia.org/wiki/2009_Princeton_Tigers_football_team / https://yalebulldogs.com/sports/football/schedule/2009 |
| 20100925-penn-at-villanova | home_team | villanova | verified_cached | https://pennathletics.com/sports/football/stats/2010/villanova/boxscore/8294 |
| 20101106-penn-at-princeton | home_team | princeton | verified_cached | https://pennathletics.com/sports/football/stats/2010/princeton/boxscore/6433 |
| 20121020-penn-at-yale | home_pts | 27 | corroborated_exports | https://en.wikipedia.org/wiki/2012_Penn_Quakers_football_team / https://pennathletics.com/sports/football/schedule/2012 / https://yalebulldogs.com/sports/football/schedule/2012 |
| 20181117-harvard-vs-yale | neutral_site | true | verified_cached | https://gocrimson.com/sports/football/schedule/2018 |
| 20210924-brown-at-harvard | date | 2021-09-24 | verified_cached | https://brownbears.com/sports/football/schedule/2021 |
| 20211105-princeton-at-dartmouth | date | 2021-11-05 | verified_cached | https://dartmouthsports.com/sports/football/schedule/2021 |
| 20261121-harvard-vs-yale | neutral_site | true | verified_cached | https://gocrimson.com/sports/football/schedule/2026 |

Raw numerical/date/site disagreements continue to appear in validation_report.md. An evidence match does not change sources_agree to true. The Cornell/Penn box-score downloads used in this review are staged separately for source-specific recovery PRs.

The Dartmouth 2000 selected score is 42-37. Its official history table and the contemporary Princeton recap agree; some later guides contain 43-37. The linked statistics document is robots-disallowed and was not fetched.

A small parser defect found during review is fixed: a recognized stat label with both values missing now warns and preserves section context. Unknown exported result strings also produce URL/raw-text warnings.

## Review outcome

In the initial pass, twenty games (21 disputed fields) had cached official evidence. Six other disputed
fields are corroborated by saved exported copies and remain at that lower evidence
tier. Raw disagreements stay visible even where the selected value is supported.
The ledger covers the 24 score/date/site-flagged games plus two OT-only cases.

The first Princeton 2000 recap request returned a challenge; no challenge content
was accepted as evidence. Dartmouth's populated history table supplied the matching
2000 row. Its linked document was blocked by robots.txt and was not fetched.
Columbia's 2008 cards omit some location/name markup and are not fully supported
yet; the relevant Princeton 2008 rows supplied the opposing official evidence.
No incomplete schedule was registered for the model build during this review.

## Expanded 2006-onward collection review

The 2018 San Diego–Harvard league box reports September 14. The cached official
Harvard schedule proves September 15 with the same teams and 36–14 final. The
selected date stays September 15; an explicit checksum-bound review preserves
the box's raw contrary date in diagnostics. Its evidence hash/time are in
`reviewed_box_dates.csv` and the field ledger. This adds one reviewed field/game
to the initial pass; neither matching copies nor a correction erase disagreement.

The expanded league pass also checks four newly disputed fields against populated
box scores with matching quarter totals: Brown was away at Stony Brook in 2009;
Penn was away at Villanova in 2011; Brown scored 34 against Holy Cross in 2009;
Brown scored 21 at Columbia in 2011. The field ledger retains each actual response
hash/time and selected value. Including the Harvard date, this expansion adds five
reviewed fields/games to the initial pass (32 fields across 31 games total).
Neutral-game home designations now follow the newly available official boxes;
team-aligned points stay unchanged for those orientation changes.
