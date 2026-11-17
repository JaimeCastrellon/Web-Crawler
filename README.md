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

The first committed processed snapshot contains **Yale's 10 games from 2004**: six with
team box-score statistics and four with scores only. It is a pipeline demonstration,
not the completed 2000–2026 dataset. The wider crawl and remaining recovery work are still pending. The validation
report describes this partial snapshot. The separate score-dataset PR is not included.
Pre-game records count completed games present in this snapshot; other teams' partial
schedules do not represent their full season records.

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
