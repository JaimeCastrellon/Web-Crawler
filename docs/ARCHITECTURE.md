# Architecture

## Goals
1. Every Ivy League football game, seasons **2000 → present** (no 2020 season).
2. Two tidy output tables (`games`, `team_game_stats`) with a `split` label and no leakage.
3. Fully reproducible from `config/` + the URL manifest; polite to source sites.

Non-goals: player-level stats, play-by-play, modeling. (Player stats can be a later extension.)

## Pipeline

```
                ┌──────────────────────────────────────────────────────────┐
config/         │ CRAWL                                                    │
sources.yaml ──▶│ discover: schedule page per (school, season)             │
                │   → box-score links (+ score-only rows from the schedule)│
                │ fetcher: robots.txt, ≥3 s/host, cache to data/raw/       │
                │ manifest: data/manifest/urls.csv                         │
                └───────────────┬──────────────────────────────────────────┘
                                ▼
                ┌──────────────────────────────┐   coverage_report.csv
                │ COVERAGE AUDIT               │──▶ school × season →
                └───────────────┬──────────────┘   full / score_only / missing
                                ▼
                ┌──────────────────────────────┐
                │ PARSE (pure, offline)        │ schedule.py → ScheduleRow[]
                │                              │ boxscore.py → ParsedBoxscore
                └───────────────┬──────────────┘
                                ▼
                ┌──────────────────────────────┐
                │ NORMALIZE                    │ teams.py: canonical team ids
                │                              │ merge.py: one row per real game
                └───────────────┬──────────────┘
                                ▼
                ┌──────────────────────────────┐
                │ VALIDATE                     │ checks.py → validation_report.md
                └───────────────┬──────────────┘
                                ▼
                ┌──────────────────────────────┐
                │ BUILD                        │ pre-game records, split labels,
                │                              │ CSVs → data/processed/
                └──────────────────────────────┘
```

Each stage reads only the previous stage's output, so any stage can be re-run alone.

## Sources

All eight schools use the Sidearm Sports platform, so URL shapes are shared:

| Page | Pattern |
|---|---|
| Schedule | `{base_url}/sports/football/schedule/{season_slug}` |
| Box score | `{base_url}/sports/football/stats/{season_slug}/{opponent_slug}/boxscore/{id}` |

`season_slug` is not uniform: most sites use `2025`, but at least Cornell uses `2004-05` for
some seasons. `sources.yaml` lists candidate patterns per school; discovery tries them in
order and records which one worked in the manifest.

Older seasons (roughly pre-2004) may have no HTML box scores; some games are linked only from
news recaps, or exist only as PDFs. The coverage audit (task 3) measures this before we
spend effort on fallbacks. Fallback order: (1) another Ivy school's copy of the same game,
(2) score-only rows from schedule pages, (3) other public sources — see `SOURCES.md`.

## Key design decisions

**Duplicates are a feature.** An Ivy-vs-Ivy game appears on both schools' sites. `merge.py`
collapses them into one game and sets `sources_agree`; disagreements go into the validation
report. Ivy-vs-non-Ivy games normally have a single source.

**`game_id`** is deterministic: `{YYYYMMDD}-{away}-at-{home}`, or
`{YYYYMMDD}-{a}-vs-{b}` (alphabetical) for neutral sites. Team parts are canonical team ids
(`yale`, `harvard`, `holy-cross`, …) from `normalize/teams.py` + `config/team_aliases.yaml`.

**`stats_level`.** `full` when a box score was parsed, `score_only` when only a schedule
result exists. Score-only games still support score-based rating models (e.g. Massey / SVD
least squares), so they are kept.

**Pre-game records** (`wins_before`, `ivy_wins_before`, …) are computed in `build.py` by
walking each team's games in date order. Records printed on box-score pages are post-game
and are never stored.

**Splits** come from `config/splits.yaml` and are applied in `build.py`. Splits are a label
and a set of per-split folders; nothing is deleted.

**Politeness.** One request at a time per host, ≥3 s apart (more if `Crawl-delay` says so),
identified User-Agent, `robots.txt` honored, everything cached. A full 2000–2026 crawl is on
the order of 8 schools × 26 seasons × ~11 pages ≈ 2,300 requests ≈ 2 hours at 3 s/request.
That is a one-time cost; rebuilds run from the cache.

The fetcher uses Protego for robots matching (including wildcards, allow precedence, and
agent-specific crawl delays). A missing robots file (404/410) permits crawling; other
unsuccessful robots responses block fetching with `RobotsDisallowed`. Transport failures
propagate. Both robots files and page responses are cached, including HTTP errors. Use
`--refresh` explicitly to retry a cached error or replace a damaged cache. Cached bodies
are checked against their SHA-256 before reuse.

Cache writes stage the body and metadata using atomic file replacements. A complete pending
metadata sidecar marks a response ready to publish. If publication is interrupted, the next
lookup verifies its hash and finishes publishing without another HTTP request. An earlier
committed response remains usable if a refresh stops before the new response is ready.
Legacy incomplete entries (a missing body/sidecar or truncated JSON) are logged and retried
as unfinished downloads; hash mismatches in complete entries still require explicit refresh.

Redirects are followed explicitly: each page destination gets its own robots check and
host delay. Redirected robots files are fetched as part of the robots lookup. The retry
limit counts retries after the initial attempt (three retries means four attempts).
Use one `Fetcher` for a crawl; it serializes calls, including concurrent callers, and keeps
per-host request times. Separate crawler processes must not run against the same host.

`Fetcher.__init__` accepts `min_delay_seconds: float | None = None` instead of the stub's
literal `3.0` default so omission reads `crawl.min_delay_seconds` from `sources.yaml`.
Explicit values still work and must be finite and at least three seconds. Injected HTTP
clients remain owned by their caller; `close()` closes only an internally created client.

`python -m ivydata fixtures [--refresh]` copies successful cached bodies into the fixture
directory and prints name/status/byte counts. HTTP errors, robots denials, and network
failures are reported with URLs and do not stop later entries. Failed captures do not
replace existing fixtures. Known Incapsula and Cloudflare challenge script/iframe URLs are
reported and skipped even on HTTP 200; the response remains in the raw cache and existing
fixtures stay intact. This detects known challenge markers, not every possible blocked or
invalid page, so captures still need human inspection. Real fixture capture is a separate
human step after task 1 merges.

**Discovery and provenance.** `crawl` expands each school's slug candidates in configured
order, skipping seasons in `skip_seasons`. It accepts HTTP 200 schedules with populated
legacy `.sidearm-schedule-game` rows or current `.s-game-card` elements. This is a page-shape
check, independent of the task 4 parser; it does not yet validate every game's date or score.
Football box-score links are resolved relative to the page, matched against the configured
path regex, and deduplicated in page order (ignoring fragments).

The URL manifest upserts by URL and sorts by `(school, season, kind, url)`. It is saved
atomically after every request; existing rows are retained on partial reruns. Robots
provenance is read from Fetcher's completed cache sidecars without additional HTTP requests.
Because the manifest has one row per URL, a shared robots URL is associated with the last
school/season visited in deterministic crawl order. `season_slug` is empty for robots.

Failures (HTTP errors, network errors, robots denials, known challenge pages, and empty
schedules) are logged with URLs and persisted to `data/reports/crawl_errors.csv`. The report
is updated atomically and retains unresolved failures across reruns, clearing a URL's error
when it succeeds. Unfetched URLs have no fabricated HTTP status in the manifest. This report
is intended as input to the later coverage and validation work. A failed box score does not
stop later links, and failed schedule candidates do not stop fallback candidates.

`crawl/pages.py` shares page-shape and challenge checks between discovery and fixture
capture. A known protection script on a populated sports page is treated as monitoring,
rather than rejecting otherwise usable schedules, box scores, and news recaps.

**Coverage audit.** `python -m ivydata coverage` reads only the manifest, crawl error
report, and raw cache; it never fetches a URL. It writes a deterministically sorted,
atomically replaced `coverage_report.csv` and prints the school-by-season F/P/S/- grid.
Every configured school and non-skipped season appears, even before it has been crawled.
Manifest columns are validated; damaged input does not replace the previous report.

Coverage uses a small DOM summary of the legacy schedule rows and current game cards:
game count, result-score presence, and box-score URLs. This is independent of the full
task 4 schedule parser, which is not yet implemented. Each box score must have a successful
manifest result, matching cached SHA-256, and recognizable box-score content; linked but
failed or unfetched pages cannot make a season `full`. Duplicate links within one game are
deduplicated, and a shared URL can count toward only one game. Dates, opponents, detailed
stats, and preseason/postseason classifications are validated by later parsing tasks.

The report uses configured slug preference when multiple schedule candidates exist. Failed
candidates and crawl errors remain visible in notes. Unknown or damaged page shapes are
logged with URLs and appear in report notes. Uncrawled seasons and future-only schedules
are distinguished in notes rather than inventing a fifth coverage level. Report counts and
notes do not create pre-game model features or copy any printed W-L records.

**Schedule parsing.** `parse_schedule` is a pure offline function returning the existing
`ScheduleParse` contract (`rows` and `warnings`). It supports legacy Sidearm rows and
current game cards. Dates are ISO strings: explicit years/ISO timestamps are checked against
the supplied football season; yearless January–March dates belong to the following calendar
year. A conflicting explicit football-schedule title rejects the page rather than relabeling
a silent redirect to the current season. Source order and raw opponent names are preserved.

Missing/unplayed results remain `None`; real zero scores remain zero. When the result letter
is omitted, W/L/T is inferred only from that game's own points. Contradictory printed results
are retained with a warning. Location comes from explicit home/away/neutral markers; Fenway
Park overrides Harvard's 2018 home designation to neutral and also handles the 2026 game.
Unknown dates, opponents, locations, and result formats generate URL/raw-text warnings and
do not prevent later rows from parsing. Multiple distinct box-score URLs retain the first
and list all alternatives in a warning; labeled legacy/PDF box-score links are also retained.
Header W-L records are never extracted.

The explicit schedule-title season check is shared by the crawler, coverage audit, and
parser. A current-season page returned for an unsupported historical URL is rejected during
discovery and coverage as well, allowing the next slug candidate to be tried.

**Box-score parsing.** `parse_boxscore` preserves its original schema and is pure/offline.
It reads legacy and current Sidearm line-score/team-statistics tables, plus archived
preformatted reports. Legacy line-score rows list away first and home second. Brown's modern tables list
the tenant school last even when it is away; the parser reads only explicit home/visiting
team names from the saved JSON state to orient scores and statistics. The source
school's hostname does not determine either team. Legacy explicit statistics
column ids also support reversed column order. Game dates come from game information,
not article publication dates. Quarter totals are checked against finals; overtime
points are summed and the number of extra periods is retained.

Missing lines remain `None`, real zeroes remain zero, and time of possession becomes
seconds. Defensive sacks made are assigned to the opponent's `sacks_allowed` and
`sack_yds_lost`; they are not copied into the team's own offensive stats. The parser
does not extract header W-L records. `turnovers` remains a later build-stage derivation
from `pass_int` and `fumbles_lost`, preserving the parser's existing field contract.
Unknown pages, malformed recognized values/rows, missing dates, and quarter mismatches
return warnings with the source URL and raw text. Coverage/challenge page-shape checks
also recognize modern box-score containers and archived reports with both team
statistics and two quarter-score lines. Alternate-source manifest integration is still
part of the remaining coverage-gap/build work.

**Normalization and merging.** Team names are matched case-insensitively through the
alias configuration after removing rankings, at/vs prefixes, and trailing numerical
records. Unknown names become lowercase ASCII slugs and are logged once; unusable
identities produce URL-bearing merge conflicts rather than fabricated team ids.

Copies are grouped by canonical team pair over a maximum one-day date span. A
three-day chain is kept separate with an ambiguity warning rather than collapsing
distinct games. Selection is deterministic: box scores before schedules, then more
complete copies, then source URL and content. Missing fields may be filled from
other copies; present values are never overwritten by a lower-priority copy.
Scores/quarters/statistics are aligned by canonical team, even if a source reverses
home/away. Box scores retain the designated home team at neutral sites; without a
box score, a neutral schedule's home designation is chosen deterministically from
the sorted team pair. Fenway is neutral. A schedule's combined venue text is not
invented into separate stadium/city values.

Each merged game retains sorted, distinct URLs actually parsed (a schedule's
unfetched box-score link is not counted as another source). `sources_agree` is empty
for a single source, and otherwise reports agreement of available dates, seasons,
team-aligned finals and home/neutral designations. Missing values alone do not create
a disagreement. Other field/statistic discrepancies are reported separately without
changing the score/date agreement flag. Parser warnings and unusable rows are also
carried into `MergeResult.conflicts` for the later validation report. A game with at
least one parsed team-statistic value is `full`; otherwise it remains `score_only`.
The result contains one game row and exactly two team rows per valid game, sorted
by date/game id/team. Pre-game records and turnovers remain build-stage work.

**Offline build.** `python -m ivydata build` reads `data/manifest/urls.csv` and
`data/manifest/recovered/*.csv`, then parses only their cached schedule/box-score
responses. `--raw-dir` and `--out-dir` override the default paths; manifests and the
build-warning report are siblings of the raw directory. No HTTP client is created.
Robots/other manifest kinds, skipped seasons, and seasons outside the configured
build range are excluded. Conflicting duplicate provenance entries fail explicitly.
Successful bodies must match the manifest SHA-256; missing/corrupt bodies abort
without replacing processed CSVs. HTTP errors, known challenges, unsupported PDFs,
wrong-season pages, and parse/merge warnings are logged and retained in the sorted
`build_warnings.csv`. A nonempty source selection with no usable games also fails
without replacing existing processed data. An empty manifest produces header-only
tables. Unmanifested cache files are not implicitly included.

Pre-game records count only rows with both final scores known, strictly before the
current date and in the same season. Same-date results are applied as a batch after
all that day's pre-game rows are computed, because kickoff times are unavailable.
Missing/unplayed scores do not become wins or games played. Counts reset by team
and season; ties and non-Ivy games are handled separately. Existing record columns
are overwritten by these computations. Records describe observed games in this
dataset; incomplete schedules (especially non-Ivy opponents) do not yield complete
season records. Header W-L records never enter the pipeline. Turnovers are derived
only when both interceptions thrown and fumbles lost are known.

Split labels come solely from the configured season ranges; skipped seasons are
removed and ambiguous/missing assignments fail. Explicit CSV schemas omit internal
parser fields, preserve empty missing cells and integer values, and write lowercase
booleans with UTF-8/LF output. All tables are rendered before publication; each file
is replaced atomically. Full tables and per-split tables are sorted by date/game id
and team where applicable. Empty splits still get headers, and repeated builds
from unchanged cache/manifests/config are byte-identical. The build-warning report
is available for task 8's validation work, which remains separate.

**Validation.** `python -m ivydata validate` checks the processed tables offline and
writes a deterministic Markdown report with counts by season/split, full/score-only
counts, and grouped errors/warnings. Existing build diagnostics are included with
their URLs. `--data-dir`, `--report`, and `--warnings-file` allow explicit paths.
Errors return a nonzero exit status; incomplete Ivy schedules and source failures
are warnings so partial historical snapshots remain reviewable.

Checks cover schema/identity, duplicate game ids and team rows, missing/orphan or
misassigned team pairs, source disagreement flags, quarter/OT totals, date/season
consistency, impossible integer/boolean values, conversion/fumble bounds, turnover
arithmetic, and incorrect Ivy flags. Negative yardage is allowed. Missing quarter
values are not treated as zero. Completed Ivy games are counted for all eight teams
in each represented historical season against the expected seven; current split
seasons are excluded from that full-season expectation. The report describes only
observed data and does not certify complete historical coverage.

CI runs `python -m ivydata validate --duplicates-only` after tests. This mode checks
processed game ids without requiring the remaining schema or replacing the report;
it skips only when no processed dataset directory exists. This independently fails
CI if committed `games.csv` contains duplicate ids.

**Recovered Brown source.** The recovery manifest includes Brown's 2004 and 2025
schedules, all twenty linked box scores, and robots provenance. All twenty boxes
were checked against schedule dates, normalized teams, and final scores, and expose
every team-stat field. The 2025 schedule uses `(RV)` and combined ranks such as
`#8/10`; normalization removes these decorations. A reduced away-game fixture
retains the explicit home/visiting identities from the JSON state with reference
indices renumbered; records, player data, and unrelated state are omitted.

The coverage audit now reads recovery manifests as well as the main manifest.
After checking cached SHA-256/status, a recovered box with parsed date/team identities
and team statistics may match a schedule row by canonical pair within one day.
Each URL counts at most once per schedule. Original failures remain in notes, and
recovery matches are identified by URL. Conflicting duplicate manifest entries fail
explicitly; wrong-season/corrupt recoveries cannot inflate coverage. A recovered
standalone box without a season schedule is noted but does not certify full-season
coverage. This extends the original direct-link audit without changing its schema.

## Module interfaces

The stub modules in `src/ivydata/` are the contract: each has typed signatures and a
docstring, and raises `NotImplementedError("Task N")` until implemented. Summary:

| module | public API | task |
|---|---|---|
| `config.py` | `load_config() -> Config` (implemented) | — |
| `crawl/fetcher.py` | `Fetcher(...).get(url) -> FetchResult`, `RobotsDisallowed` | 1 |
| `crawl/discover.py` | `schedule_url_candidates`, `find_boxscore_links`, `crawl` | 2 |
| `crawl/manifest.py` | `Manifest(path).record(...)`, `.save()` | 2 |
| `crawl/coverage.py` | `coverage_level`, `build_coverage_report` | 3 |
| `parse/schedule.py` | `parse_schedule(html, school, season, page_url) -> ScheduleParse` | 4 |
| `parse/boxscore.py` | `parse_boxscore(html, page_url) -> ParsedBoxscore` | 5 |
| `normalize/teams.py` | `canonical_team_id(raw, aliases)`, `is_ivy` | 6 |
| `normalize/merge.py` | `make_game_id`, `merge_games(...) -> MergeResult` | 6 |
| `build.py` | `add_pregame_records`, `assign_splits`, `build` | 7 |
| `validate/checks.py` | `run_checks(...) -> list[Issue]`, `write_report` | 8 |
