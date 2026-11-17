# Test fixtures

Saved HTML pages that parser tests run against, so tests never hit the network.

To (re)capture them, from the repo root on a machine with internet access:

```bash
python -m ivydata fixtures
git add tests/fixtures/*.html && git commit -m "Add HTML fixtures"
```

The URL list is `fixtures.yaml`. Keep fixtures few and small — add one only when a parser
needs a new page shape (e.g. an overtime game, an old-format season, a neutral site).

The command prints each name, HTTP status, and byte count. Missing pages, robots denials,
and network failures are reported and later entries continue; only HTTP 200 bodies are
saved. Failed captures leave existing fixtures in place. Responses (including errors) are
reused from `data/raw/`; use `python -m ivydata fixtures --refresh` to explicitly refetch.

Known Incapsula and Cloudflare challenge scripts/iframes are reported and skipped even when
the site returns HTTP 200. These responses remain in the raw cache; they do not create or
overwrite fixtures. Inspect successful captures too, since unknown challenge pages may not
be detected.

## Committed schedule excerpts

Captured through Fetcher on 2026-11-16, then reduced to the schedule game elements so the
repo contains small parser fixtures rather than full navigation, ads, and scripts. Text,
game attributes, dates, scores, and links within the retained elements are unchanged.

| fixture | source | retained elements |
|---|---|---|
| `schedule_yale_2025.html` | `https://yalebulldogs.com/sports/football/schedule/2025` | all 12 `.sidearm-schedule-game` rows |
| `schedule_yale_2004.html` | `https://yalebulldogs.com/sports/football/schedule/2004` | all 10 `.sidearm-schedule-game` rows, 9 box-score links |
| `schedule_brown_2025_excerpt.html` | `https://brownbears.com/sports/football/schedule/2025` | first 2 `.s-game-card` elements |
| `schedule_harvard_2018_fenway.html` | `https://gocrimson.com/sports/football/schedule/2018` | Yale game row; listed home by source but played at Fenway |
| `schedule_harvard_2026_upcoming.html` | `https://gocrimson.com/sports/football/schedule/2026` | upcoming Yale game row at Fenway, no result |

Recapturing creates full local pages; reduce them to these elements before committing.
Harvard's 2025 box-score URL returned an empty Incapsula challenge and is not included.

## Committed box-score excerpts

Captured through Fetcher on 2026-11-16. URLs are recorded by matching fixture name
in `fixtures.yaml`. Legacy/current excerpts retain the line-score table, team-statistics
table, and game information; archived reports retain their scoring/team-statistics `pre`
blocks. Navigation, scripts, images, and unrelated attributes were removed. Re-capture
produces full local pages; curate them again before committing. Full cached pages and
these excerpts produce identical parser output for all eight examples.

| fixture | layout / notable case |
|---|---|
| `boxscore_yale_2025_harvard.html` | legacy; Harvard–Yale 2025, Yale official copy |
| `boxscore_yale_2024_dartmouth.html` | legacy; one overtime period |
| `boxscore_penn_2004_yale.html` | legacy; Penn hosts the page but Yale is home |
| `boxscore_cornell_2004_yale.html` | legacy; source uses the `2004-05` slug |
| `boxscore_brown_2004_yale.html` | modern Sidearm tables and game information |
| `boxscore_columbia_2004_yale.html` | archived text report |
| `boxscore_harvard_2004_yale.html` | archived text report |
| `boxscore_dartmouth_2004_yale.html` | archived text report; game date differs from article date |

Task 5 originally requests Harvard's 2025 copy. That URL returns an Incapsula challenge,
so the fixture uses Yale's official copy of the same game rather than labeling a
challenge as data. Harvard's original URL stays in the capture list for future retries.
Missing rushing/passing TD lines in the Columbia/Dartmouth archived team totals stay
`None`; they are not inferred from player statistics or scoring plays. Printed header
records remain source text only and are never extracted.
