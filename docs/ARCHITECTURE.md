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
