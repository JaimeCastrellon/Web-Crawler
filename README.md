# Ivy League Football Dataset (2000–present)

An open, reproducible dataset of every Ivy League football game since the 2000 season,
built by a polite web crawler + scraper over the schools' official athletics sites.

The dataset exists to support a downstream modeling project: predicting **The Game**
(Harvard vs. Yale) with linear-algebra methods (SVD / least-squares ratings). This repo is
the **data collection and cleaning** half of that project; modeling lives elsewhere and
consumes the files in `data/processed/`.

> No public, game-level Ivy League football dataset covering 2000+ with team box-score stats
> appears to exist, so we are building one.

## What you get

| File | One row per | Notes |
|---|---|---|
| `data/processed/games.csv` | game | scores, quarters, site, neutral flag, `split`, `stats_level` |
| `data/processed/team_game_stats.csv` | team per game | yards, turnovers, downs, possession, **pre-game** records |
| `data/processed/{train,test,current}/` | — | the same two tables, pre-split by season |
| `data/reports/coverage_report.csv` | school × season | what was found: full box score / score only / missing |
| `data/reports/validation_report.md` | — | cross-source checks and anomalies |
| `data/manifest/urls.csv` | fetched URL | provenance: url, status, fetched_at, sha256 |

Column definitions: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

### Train / test split (for the modeling team)

Defined in [`config/splits.yaml`](config/splits.yaml):

| split | seasons | purpose |
|---|---|---|
| `train` | 2000–2023 | fit models |
| `test` | 2024–2025 | held out — predict these before touching 2026 |
| `current` | 2026 | season in progress, used for the final 2026 prediction |

There was no Ivy League football season in 2020.

**No leakage:** every column in a row is knowable *before* that game kicked off, except the
game's own result. Records shown on athletics-site box scores are *post*-game and are never
copied; pre-game records are recomputed from earlier rows.

## How it works

```
config/sources.yaml ─▶ crawl (schedule pages → box-score links, cached, rate-limited)
                    ─▶ parse (HTML → rows)  ─▶ normalize (team names, merge duplicates)
                    ─▶ validate             ─▶ build (splits, pre-game records, CSVs)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Sources and crawl etiquette:
[`docs/SOURCES.md`](docs/SOURCES.md). Work plan: [`docs/TASKS.md`](docs/TASKS.md).

## Current data coverage

The processed snapshot contains **29 games** from Yale 2004 and Brown 2004/2025:
25 with team box-score statistics and four score-only. Coverage verifies three of
the 208 configured school-seasons: Brown 2004/2025 are full, Yale 2004 is partial.
The broader 2000–2026 crawl and recovery work remain; the separate proposed
1,355-game scores dataset is not integrated. The validation report describes this
partial snapshot. Pre-game records count completed games present in it; partial
opponent schedules do not yield complete season records.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # offline tests against saved HTML fixtures
python -m ivydata crawl     # fetch (polite, cached in data/raw/, not committed)
python -m ivydata build     # offline parse → merge → pre-game records → data/processed/
python -m ivydata validate  # quality checks + data/reports/validation_report.md
```

The build uses only the local cache and the main/recovered URL manifests. A fresh
checkout has no raw pages: retrieve the manifested sources and record their current
provenance before building. Missing/corrupt successful cache entries stop the build and
preserve existing processed files. Rebuilds with unchanged cache and manifests are
byte-identical. See `data/reports/build_warnings.csv` for source failures and parse/merge
diagnostics. `validate` returns nonzero for data errors; coverage/source warnings
remain visible without treating a partial snapshot as a complete historical dataset.

## How this repo is built

Design and review by Claude Code; implementation by Codex, one GitHub issue per PR.
Agent instructions live in [`AGENTS.md`](AGENTS.md).

## License & attribution

Code: MIT (see `LICENSE`). The data are factual game results and statistics compiled from
the Ivy League schools' official athletics websites (see `docs/SOURCES.md`); please credit
those sources and this repository when you use them. Raw HTML is not redistributed.
