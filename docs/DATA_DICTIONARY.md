# Data dictionary

Conventions: CSV, UTF-8, header row. Dates `YYYY-MM-DD`. Booleans `true`/`false`.
Missing = empty cell (never `0`). Team ids are lowercase slugs (`yale`, `holy-cross`).

## `games.csv` — one row per game

| column | type | description |
|---|---|---|
| `game_id` | str | `{YYYYMMDD}-{away}-at-{home}`, or `{YYYYMMDD}-{a}-vs-{b}` (alphabetical) at neutral sites |
| `season` | int | season year (fall), e.g. `2025` |
| `date` | date | game date (local) |
| `home_team` | str | canonical team id (for neutral sites: the team listed as home by the source) |
| `away_team` | str | canonical team id |
| `neutral_site` | bool | `true` if neither team played at its home stadium (e.g. Harvard–Yale at Fenway 2018, 2026) |
| `stadium` | str | as printed by source |
| `city` | str | as printed by source |
| `home_pts`, `away_pts` | int | final score (empty for not-yet-played `current` games) |
| `home_q1`…`home_q4`, `away_q1`…`away_q4` | int | points by quarter |
| `home_ot`, `away_ot` | int | total overtime points (empty if no OT) |
| `num_ot` | int | number of overtime periods (0 if none) |
| `ivy_game` | bool | both teams are Ivy League members |
| `attendance` | int | as printed |
| `stats_level` | str | `full` (at least one box-score team-statistic value parsed) or `score_only` (no team statistics) |
| `split` | str | `train` / `test` / `current` from `config/splits.yaml` |
| `sources_agree` | bool | agreement of available dates, seasons, team-aligned finals and home/neutral designations across sources; empty if one source |
| `source_urls` | str | `|`-separated URLs used |

## `team_game_stats.csv` — one row per team per game (two rows per game)

Identity and context:

| column | type | description |
|---|---|---|
| `game_id`, `season`, `date`, `split`, `stats_level` | | copied from `games` |
| `team`, `opponent` | str | canonical team ids |
| `is_home` | bool | team is `home_team` in `games` |
| `neutral_site` | bool | copied |
| `points`, `points_allowed` | int | final score from this team's perspective |

Pre-game context (computed from earlier rows only; **never** from box-score headers):

| column | type | description |
|---|---|---|
| `games_before` | int | games this team played earlier in the same season |
| `wins_before`, `losses_before`, `ties_before` | int | season record entering the game |
| `ivy_wins_before`, `ivy_losses_before` | int | Ivy record entering the game |

Non-Ivy opponents' pre-game record fields are empty because their full schedules
are not collected. Their observed Ivy matchups cannot establish true season records.

Box-score team stats (empty when `stats_level = score_only`):

| column | type | description |
|---|---|---|
| `first_downs` | int | |
| `rush_att`, `rush_yds`, `rush_td` | int | |
| `pass_cmp`, `pass_att`, `pass_yds`, `pass_td`, `pass_int` | int | `pass_int` = interceptions thrown |
| `total_plays`, `total_yds` | int | |
| `fumbles`, `fumbles_lost` | int | |
| `turnovers` | int | `pass_int + fumbles_lost` |
| `penalties`, `penalty_yds` | int | |
| `third_down_conv`, `third_down_att` | int | |
| `fourth_down_conv`, `fourth_down_att` | int | |
| `sacks_allowed`, `sack_yds_lost` | int | if reported; sack yardage is signed net loss and can be negative when the recorded play gains yards |
| `punts`, `punt_yds` | int | |
| `time_of_possession_s` | int | seconds |

## `coverage_report.csv` — one row per (school, season)

| column | description |
|---|---|
| `school`, `season` | |
| `schedule_url` | the URL that worked (empty if none) |
| `season_slug` | which slug pattern worked |
| `games_on_schedule` | rows found on the schedule page |
| `boxscores_found` | games with a distinct linked or date/team-matched recovered, successfully fetched, checksum-verified box-score page in the manifest/cache |
| `level` | `full` (all games have usable cached box scores), `partial` (some do), `score_only` (no usable box scores but schedule results exist), `missing` (no result data available) |
| `notes` | free text, e.g. "box scores linked only from news recaps" |

Coverage measures available downloads, not merely link presence. A 404/5xx response,
challenge, unfetched link, missing/corrupt body, or unrecognized box-score page is excluded
from `boxscores_found` and described with its URL in `notes`. One box-score URL cannot
satisfy multiple games. This refines the original link-count description while preserving
the report's columns. `full` verifies recognizable box-score content; detailed stat parsing
and validation happen in later tasks.

Uncrawled school-seasons are marked `missing` with a "not crawled" note. A future-only
schedule with neither results nor usable box scores also has level `missing`, but retains
its schedule URL, slug, and game count with an explanatory note. There is no 2020 row.

## `data/manifest/urls.csv` — one row per fetched URL

`url, school, season, kind (schedule|boxscore|robots), status, fetched_at, sha256, season_slug`

The conference recovery manifest uses the same columns. Its additional
`league_index` and `league_rejected` kinds preserve discovery/rejected-response
provenance and are excluded from game parsing. Those and robots rows use source
label `league`; accepted boxscore rows name a participating Ivy school.

`data/reports/league_recovery_errors.csv` uses the same five columns as
`crawl_errors.csv` below. It retains unresolved league index/download/identity
failures and removes them on successful retries. Offline build includes these
URL-bearing failures in `build_warnings.csv`, hence the validation report.

School recoveries use the same error schema in
`data/reports/recovery_errors/<source>_2006_2008.csv`. All such files are included
in build/validation diagnostics. Their attempt inventories under
`data/reports/recovery/` distinguish accepted boxes, discovery pages, rejected
responses and deferred/unfetched URLs. Unfetched attempts have empty status/hash/
timestamp cells; they are never represented as successful downloads or zero stats.

## `data/reports/crawl_errors.csv` — unresolved crawl failures, one row per URL

| column | description |
|---|---|
| `url` | requested URL, including failed schedule candidates |
| `school`, `season` | context of the most recent attempt |
| `kind` | `schedule` or `boxscore` |
| `error` | HTTP status, exception type/message, known bot challenge, or unrecognized schedule shape |

Rows are sorted by (`school`, numeric `season`, `kind`, `url`). Successful retries remove
their error row; failures outside the current selection remain. Requests that fail before
an HTTP response exists appear here without a fabricated manifest status. Robots responses
are recorded in the URL manifest using their actual cached status.

## `data/reports/build_warnings.csv` — offline build diagnostics

| column | description |
|---|---|
| `source_url` | source URL for download/cache/parse diagnostics; empty for merge messages that contain their source URLs within the message |
| `message` | HTTP/cache failure, unsupported or wrong-season page, parse warning, or merge conflict with source context |

Rows are deduplicated and sorted by (`source_url`, `message`). This is an input to the
validation report, not a model feature. It is written even when missing/corrupt successful
cache entries prevent replacing the processed tables. Structural manifest errors fail
explicitly before processing. Pre-game counts cover completed games actually present
in the dataset, strictly on earlier dates; incomplete schedules imply incomplete records.

Coverage also reads `data/manifest/recovered/*.csv` using the same URL-manifest schema.
A recovered page may count for another school's schedule only after parsing its game
date/team identities and team statistics and matching the canonical pair within one
day. Original download errors and the matched recovery URLs remain visible in notes.

## `data/manifest/score_sources.csv` — saved factual row provenance

`url, school, season, kind (official_export|wikipedia), status, fetched_at, revision_id,
export_path, export_sha256, payload_sha256, games_found`

`status` and `fetched_at` are the saved export's acquisition metadata. `export_sha256`
hashes the saved file, and `payload_sha256` hashes the canonical JSON page object
(sorted keys, ASCII escapes, compact separators). They are not raw HTML-response
hashes. Wikipedia entries retain revision ids and attribution. Default source paths
are repository-relative; explicitly supplied external files retain their actual path.

## `data/reports/score_coverage.csv` — mixed-source score inventory

`school, season, schedule_sources, games_in_dataset, games_with_scores, games_with_stats,
source_disagreements`

Sources are pipe-separated provenance tiers; only successful nonempty exports count.
`games_with_stats` counts actual parsed box-score data, not discovered links. This
inventory is separate from the download-based `coverage_report.csv`.

`data/manifest/boxscore_urls.txt` is a deduplicated discovery list from row exports.
An entry alone does not establish that it was downloaded or parsed, and unfetched
links are excluded from `games.source_urls`.

## `data/reports/source_review.csv` — field-level review ledger

`data/manifest/reviewed_box_dates.csv` contains explicit, evidence-checked date
corrections with columns `url, original_date, date, school, evidence_url,
evidence_sha256, evidence_fetched_at`. Evidence must be a cached official schedule
matching the game teams/finals, and the correction is limited to one day within
the same football season. Original box dates remain visible as disagreements.
These review fields are provenance, not additional model columns.

`game_id, field, selected_value, review_status, evidence_url, evidence_sha256,
evidence_fetched_at, notes`

`selected_value` matches the current games.csv field. `verified_cached` records
checks against a populated, checksum-verified official page; `corroborated_exports`
means matching saved row exports and is a lower evidence tier. Export support URLs
are pipe-separated. The cached evidence hash/time are filled only for cached
verification. Reviews preserve raw source disagreements; the ledger is not a
model feature and does not change sources_agree to true.

## Reviewed PDF excerpt input

Optional `data/manifest/reviewed_boxscores.json` is a list of factual game
excerpts. Each object has exactly `url`, `school`, `season`, `source_sha256`,
`source_fetched_at`, `evidence_page` (one-based), `evidence_region`,
`review_method` (`visual_cached_pdf`), `game`, and `team_stats`. The game and two
team objects use only the existing `ParsedBoxscore` fields described above.
Omitted fields stay missing; the excerpt never supplies pre-game records.

A recovered manifest row of kind `reviewed_boxscore` records the complete source
PDF's successful response. Its checksum and fetch time must match the excerpt
and the local raw cache. The page/region pointer records the visual review; it
is not a claim that a generic PDF parser independently verified every number.
The output game/team CSV schemas are unchanged.
