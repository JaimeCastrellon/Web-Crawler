# Ivy League Football Dataset (2000–present)

An open, reproducible dataset of every Ivy League football game since the 2000 season,
built by a polite web crawler + scraper over the schools' official athletics sites.

The dataset exists to support a downstream modeling project: predicting **The Game**
(Harvard vs. Yale) with linear-algebra methods (SVD / least-squares ratings). This repo is
the **data collection and cleaning** half of that project; modeling lives elsewhere and
consumes the files in `data/processed/`.

> No public, game-level Ivy League football dataset covering 2000+ with team box-score stats
> appears to exist, so we are building one.

## Status (2026-11-16)

**v0.1-data is built:** every game from 2000 through the 2026 regular season — **1,355 games**
(26 seasons × 28 Ivy games + non-conference + 2025 FCS playoff games), final scores,
home/away/neutral, pre-game records and `train`/`test`/`current` splits. Box-score stats
(quarters, yards, turnovers…) are the next pass.

Sources: Yale, Cornell and Penn's official athletics sites (crawled at their robots.txt
`Crawl-delay` of 30 s) plus Wikipedia team-season articles for all eight schools. Harvard,
Brown, Columbia, Dartmouth and Princeton's sites block automated access, so games among those
five come from Wikipedia. 963 games have two or more independent copies; 22 disagree and are
listed in `data/reports/validation_report.md`, with official-site values used where available.

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

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # offline tests against saved HTML fixtures
# rebuild the score-level dataset from the saved source exports
python -m ivydata scores \
  --official data/sources/ivy_official_{cornell,penn,yale}.json \
  --wikipedia data/sources/ivy_wikipedia_schedules.json
```

## How this repo is built

Design and review by Claude Code; implementation by Codex, one GitHub issue per PR.
Agent instructions live in [`AGENTS.md`](AGENTS.md).

## License & attribution

Code: MIT (see `LICENSE`). The data are factual game results and statistics compiled from
the Ivy League schools' official athletics websites (see `docs/SOURCES.md`); please credit
those sources and this repository when you use them. Raw HTML is not redistributed.
