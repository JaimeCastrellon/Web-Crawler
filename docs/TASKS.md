# Work plan

Each `## Task` below is mirrored as a GitHub issue. Codex picks up one issue at a time
(see `AGENTS.md` for the PR workflow); Claude Code reviews each PR against the acceptance
criteria here.

**Milestones**
- **v0.1-data (scores, 2000–2026)** — tasks 1, 2, 3, 4, 6, 7. Enough for score-based rating
  models. Target: Wed 2026-11-18, so the modeling team has time before The Game
  (Sat 2026-11-21, Fenway Park).
- **v1.0-data (box-score stats)** — tasks 5, 8, 9.

Dependency order: 1 → 2 → 3; 1 → 4, 5 (need fixtures); 4 + 5 → 6 → 7 → 8; 3 → 9.

---

## Task 1: Fetcher (polite HTTP + cache) and fixture capture

Implement `ivydata.crawl.fetcher.Fetcher` and the `fixtures` CLI command.

- `Fetcher.get(url)`: return cached response if present (unless `refresh=True`); else check
  `robots.txt` for the host (cache the parsed robots per host), sleep so requests to the same
  host are ≥ `min_delay_seconds` apart (respect a larger `Crawl-delay`), GET with the
  configured User-Agent, retry 429/5xx up to 3 times with exponential backoff, write body to
  `data/raw/<host>/<sha1(url)>.html` plus a sidecar `.json` (url, status, fetched_at, sha256).
- Disallowed by robots → raise `RobotsDisallowed`; 404 → return result with status 404
  (not an exception).
- `python -m ivydata fixtures`: fetch every URL in `tests/fixtures/fixtures.yaml` through the
  `Fetcher` and copy each body to `tests/fixtures/<name>.html`. Print a table of
  name / status / bytes. Missing pages are reported, not fatal.

**Acceptance**
- [ ] Unit tests use `httpx.MockTransport` (no network): cache hit makes no request; two
      requests to one host are spaced ≥ delay (inject a fake clock/sleep); robots disallow
      raises; 503 then 200 retries and succeeds; 404 returned not raised.
- [ ] `min_delay_seconds` default comes from `config/sources.yaml` (`crawl.min_delay_seconds`).
- [ ] **Human step after merge:** run `python -m ivydata fixtures` locally and commit the
      HTML files in `tests/fixtures/`. (Codex's sandbox may not have internet access.)

## Task 2: Discovery, manifest, and `crawl` command

- `schedule_url_candidates(school, season)`: expand `season_slug_patterns` from
  `sources.yaml` into URLs, in order.
- `find_boxscore_links(html, page_url)`: absolute, de-duplicated box-score URLs
  (`/sports/football/stats/.../boxscore/<id>`), in page order.
- `Manifest`: load/append/save `data/manifest/urls.csv` (columns in `DATA_DICTIONARY.md`),
  stable sort by (`school`, `season`, `kind`, `url`).
- `python -m ivydata crawl [--schools yale,harvard] [--seasons 2000-2026] [--refresh]`:
  for each (school, season) — skip seasons in `splits.yaml: skip_seasons` — try schedule
  candidates until one returns 200 with ≥ 1 game, then fetch every box-score link.
  Resumable: interrupted runs continue from the cache.

**Acceptance**
- [ ] Link extraction tested on schedule fixtures (2025 and 2004 pages).
- [ ] Slug fallback tested (first candidate 404 → second used; recorded in manifest).
- [ ] Crawl loop tested end-to-end with a fake `Fetcher`.

## Task 3: Coverage audit

`python -m ivydata coverage` → `data/reports/coverage_report.csv` (columns in
`DATA_DICTIONARY.md`), built from the manifest and parsed schedules. Also print a compact
school × season grid (`F` full, `P` partial, `S` score-only, `-` missing).

**Acceptance**
- [ ] Level logic unit-tested (all games have box scores → `full`; some → `partial`; none
      but schedule has scores → `score_only`; no schedule → `missing`).
- [ ] Report is deterministic and committed after the first real crawl.

## Task 4: Schedule parser (score-only rows)

`parse_schedule(html, school, season, page_url) -> list[ScheduleRow]`. Each row: date,
opponent (raw name), home/away/neutral, venue text, result (W/L/T), team points, opponent
points, box-score URL if linked. Unplayed games → points empty.

**Acceptance**
- [ ] Tested on at least: a 2025 schedule, a 2004 schedule, and a page with an
      unplayed future game.
- [ ] Neutral-site detection works for Harvard–Yale at Fenway (2018 and 2026).
- [ ] Unparseable rows are returned in a `warnings` list with the raw text, not dropped.

## Task 5: Box-score parser

`parse_boxscore(html, page_url) -> ParsedBoxscore` with `.game` (date, teams, site,
stadium, attendance, quarter and OT scores, finals) and `.team_stats` (two dicts with the
box-score columns in `DATA_DICTIONARY.md`). Do **not** extract the W-L records in the
header.

**Acceptance**
- [ ] Fixture tests with exact expected values for: Harvard–Yale 2025 (gocrimson), the
      Dartmouth–Yale 2024 overtime game (yalebulldogs), Penn–Yale 2004 (pennathletics),
      and Cornell–Yale 2004 (cornellbigred, `2004-05` slug).
- [ ] Quarter sums equal finals in every fixture; OT handled.
- [ ] Missing stat lines → empty, not 0. Time of possession converted to seconds.

## Task 6: Team normalization and game merge

- `canonical_team_id(raw)`: lowercase slug via `config/team_aliases.yaml`
  ("Yale University", "YALE", "Yale" → `yale`). Unknown names → slugify + log once.
- `merge_games(boxscores, schedule_rows)`: one record per real game, `game_id` per
  `ARCHITECTURE.md`. Two copies of the same game (same date ±1 day, same team pair) merge;
  box score beats schedule row; disagreements recorded, `sources_agree=false`.

**Acceptance**
- [ ] Tests: two Ivy copies merge to one; score mismatch flagged; non-Ivy single source;
      neutral-site `game_id` uses `-vs-` and alphabetical order.

## Task 7: Build — pre-game records, splits, CSVs

`python -m ivydata build` → `data/processed/games.csv`, `team_game_stats.csv`, and
`train/ test/ current/` sub-folders, per `DATA_DICTIONARY.md`.

**Acceptance**
- [ ] Pre-game records: a team's first game of a season has all `*_before = 0`; a test
      confirms the record for game *n* counts only games 1…n-1.
- [ ] No column copied from box-score headers' W-L records (test asserts the parser output
      has no such field).
- [ ] Split labels from `splits.yaml`; 2020 absent; reruns produce byte-identical CSVs.

## Task 8: Validation report

`python -m ivydata validate` → `data/reports/validation_report.md`: counts per season and
split; every game with `sources_agree=false`; quarter-sum mismatches; teams with ≠ expected
Ivy games per season (7 for full Ivy seasons); duplicate `game_id`s; impossible values
(negative yards are fine, negative attempts are not); parse warnings with URLs.

**Acceptance**
- [ ] Each check has a unit test with a synthetic bad row.
- [ ] CI fails if `data/processed/` exists and has duplicate `game_id`s.

## Task 9: Fill coverage gaps (after task 3's report)

Driven by `coverage_report.csv`. For each `missing`/`score_only` school-season: try the
opponent's copy, news-recap "Box Score" links, then other public sources per
`SOURCES.md`. Separate PR per source.
