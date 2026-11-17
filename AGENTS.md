# AGENTS.md — instructions for coding agents (Codex, Claude Code)

Read this file, then `docs/ARCHITECTURE.md` and `docs/DATA_DICTIONARY.md`, before writing code.

## Project in one paragraph
Crawl the eight Ivy League athletics websites (config in `config/sources.yaml`), collect every
football game from the 2000 season onward, parse schedule and box-score pages into two tidy
tables (`games`, `team_game_stats`), merge the duplicate copies of Ivy-vs-Ivy games, validate,
and write CSVs to `data/processed/`. The output feeds a separate SVD-based model that predicts
Harvard–Yale. This repo is **data only** — no modeling code.

**Collection scope (user decision, 2026-11-17):** retain the older rows already collected,
but new collection targets **2006–2026**, newest seasons first. Do not spend new requests
on 2000–2005 gaps, including the previously tracked Yale 2004 gaps. The dataset/split
start stays 2000 to retain existing history; it is not the new collection boundary.

## Setup & commands
```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest -q
python -m ivydata --help
```
Python ≥ 3.11. Type hints on all public functions. Dependencies are declared in
`pyproject.toml`; add new ones there, sparingly.

## Workflow
- One GitHub issue → one branch → one PR. Branch name: `codex/<issue-number>-<short-slug>`.
- PR description: `Closes #<n>`, what changed, how it was tested, any schema change.
- Every PR must pass CI (ruff + pytest). Add tests for every new function.
- Keep the public interfaces in the stub modules (signatures + docstrings). If an interface
  must change, say why in the PR and update `docs/ARCHITECTURE.md` in the same PR.
- Any change to an output column requires the same PR to update `docs/DATA_DICTIONARY.md`.

## Hard rules
1. **Tests never touch the network.** Parsers are pure functions `html: str -> rows` and are
   tested against files in `tests/fixtures/`. Mark any live check `@pytest.mark.live`
   (skipped by default).
2. **Be polite to the source sites.** All HTTP goes through `ivydata.crawl.fetcher.Fetcher`.
   Do not lower `min_delay_seconds` (≥ 3 s per host), do not parallelize requests to the same
   host, honor `robots.txt`, and always use the configured User-Agent. Cache every response
   in `data/raw/`; never re-fetch a cached URL unless `--refresh` is passed.
3. **Never commit `data/raw/`** (it is gitignored). Commit `data/manifest/`, `data/processed/`,
   `data/reports/`, and small fixture files only.
4. **No leakage.** No column in a row may depend on information from after that game's
   kickoff, other than that game's own result columns. In particular, do **not** store the
   W-L records printed in box-score headers (they are post-game). Pre-game records are
   computed in `ivydata.build` from earlier games only.
5. **Never drop data silently.** If a page can't be parsed, log it and record it in the
   validation report with the URL; don't skip it without a trace.
6. **Determinism.** Same raw cache → byte-identical CSVs. Sort rows by (`date`, `game_id`,
   `team`). Dates are ISO `YYYY-MM-DD`. Missing values are empty cells, not `0`.

## Layout
```
config/            sources.yaml, splits.yaml, team_aliases.yaml
src/ivydata/
  config.py        load + validate YAML config (implemented)
  crawl/           fetcher.py, discover.py, manifest.py, coverage.py
  parse/           schedule.py, boxscore.py
  normalize/       teams.py, merge.py
  validate/        checks.py
  build.py         pipeline orchestration, splits, pre-game records, CSV writing
  cli.py           `python -m ivydata {crawl,coverage,build,validate}`
tests/fixtures/    saved HTML pages (see tests/fixtures/README.md)
data/              raw/ (ignored), manifest/, processed/, reports/
docs/              ARCHITECTURE.md, DATA_DICTIONARY.md, SOURCES.md, TASKS.md
```
