# Sources and crawl etiquette

## Primary sources — official athletics sites (Sidearm Sports)

| school | base URL | verified example |
|---|---|---|
| Brown | https://brownbears.com | |
| Columbia | https://gocolumbialions.com | `/sports/football/schedule/2025` (HTTP 200, checked 2026-11-16) |
| Cornell | https://cornellbigred.com | `/sports/football/stats/2004-05/yale-university/boxscore/4180` |
| Dartmouth | https://dartmouthsports.com | |
| Harvard | https://gocrimson.com | `/sports/football/stats/2025/yale-university/boxscore/32128` |
| Penn | https://pennathletics.com | `/sports/football/stats/2004/yale/boxscore/10596` |
| Princeton | https://goprincetontigers.com | |
| Yale | https://yalebulldogs.com | `/sports/football/stats/2024/dartmouth/boxscore/18407` |

Base URLs are configured in `config/sources.yaml`.

### Task 1 live verification (2026-11-16)

Checks use `Fetcher` with the configured User-Agent and each site's robots rules. Responses
stay in the ignored raw cache. The checked page on each host is
`/sports/football/schedule/2025`; this verifies connectivity and page content, not parsing.
All eight robots responses returned HTTP 200.

| school | schedule response | observation |
|---|---|---|
| Brown | 200 | football schedule content |
| Columbia | 200 | football schedule content; base URL confirmed |
| Cornell | 200 | football schedule content |
| Dartmouth | 200 | football schedule content |
| Harvard | 200 | 212-byte Incapsula script challenge; no schedule content |
| Penn | 200 | football schedule content |
| Princeton | 200 | football schedule content |
| Yale | 200 | football schedule content |

HTTP 200 alone does not prove a usable fixture. Inspect captured pages before committing
fixtures, especially Harvard's. A cached challenge response requires an explicit
`--refresh` to replace. Do not bypass site access controls.

### Score-level crawl from a browser (2026-11-16)

Every site's `robots.txt` allows `/sports/` and sets **`Crawl-delay: 30`** (now the
configured minimum). The v0.1 score build crawled schedule pages from a browser tab on each
site (`tools/browser/sidearm_schedule_crawler.js`), one request per 31 s per host:

| school | browser-tab crawl result | used in v0.1 |
|---|---|---|
| Cornell | ok, 2000–2026 (slug `2004-05`) | official |
| Penn | ok, 2000–2026 | official |
| Yale | ok, 2000–2026 | official |
| Harvard | Imperva/Incapsula challenge | Wikipedia |
| Brown, Columbia, Dartmouth, Princeton | Imperva/Incapsula challenge to the browser tab, although the Python `Fetcher` above received schedule content | Wikipedia |
| (league) ivyleague.com | Imperva/Incapsula challenge; robots also asks for `Visit-time: 0100-0645` | — |

So Brown, Columbia, Dartmouth and Princeton can likely be crawled with `python -m ivydata
crawl` (Harvard cannot). Doing so would make their games official-primary in the next build.
**We do not attempt to get past bot protection;** `crawlable: false` in
`config/sources.yaml` marks Harvard.

## Secondary source — Wikipedia

Team-season articles (`{year} {School} {Mascot} football team`) carry schedule/result tables,
either as `{{CFB schedule entry}}` templates (≈2011+) or as older positional
`{{CFB schedule}}` rows. All 208 school-seasons (8 × 2000–2026, no 2020) exist. Fetched via the
MediaWiki API (`action=query&prop=revisions`, 40 titles per request, 1.5 s apart, with an
`Api-User-Agent`) by `tools/browser/wikipedia_schedule_export.js`. Content is CC BY-SA 4.0;
the revision id of every page used is recorded in `data/manifest/score_sources.csv`.

**Precedence:** official athletics site > Wikipedia. Every game lists all sources that had it
(`sources`), the one used (`primary_source`), and whether they agreed (`sources_agree`).
Wikipedia pages disagree with each other on a handful of 2000–2012 games (home/away or a
score); where an official page covers the game, it settles it.

## Known quirks
- **First bounded crawl (2026-11-16):** Yale 2004 has 10 schedule rows with results and
  9 box-score links. All 9 linked Yale box-score URLs returned HTTP 500 after the fetcher's
  normal retry behavior. The committed manifest and crawl error report retain each URL;
  coverage is `score_only`. This is one school-season probe, not a completed 2000–2026
  crawl. Other school-seasons in the first coverage report are explicitly "not crawled".
- **Season slugs differ** (`2004` vs `2004-05`). Discovery tries each pattern in
  `sources.yaml`.
- **Older seasons** (≈ pre-2004) may lack HTML box scores. Some older games are linked only
  from news recap pages (e.g. Yale's 2004 recaps link "Box Score"/"Final Stats").
- **Box-score headers show post-game records** (e.g. "Harvard (9-1, 6-1)" on the page for the
  game Harvard lost). Never store them.
- **Neutral sites**: Harvard–Yale was at Fenway Park in 2018 and is again on
  2026-11-21. Set `neutral_site = true`.
- **No 2020 season** (Ivy League cancelled fall 2020 competition).

## Fallbacks (only after the coverage audit shows a gap)
1. The opponent Ivy school's copy of the same game.
2. Score-only rows from schedule pages (`stats_level = score_only`).
3. Other public sources (e.g. ESPN box scores exist for many mid-2000s Ivy games). Check the
   site's terms and robots.txt first; prefer a different source if they prohibit automated
   access. Record any fallback source in `source_urls`.

## Etiquette (enforced in `Fetcher`)
- Honor `robots.txt` and any `Crawl-delay` (30 s on all Ivy sites).
- One request at a time per host, ≥ `min_delay_seconds` apart.
- User-Agent: `ivy-football-data/0.1 (+https://github.com/JaimeCastrellon/Web-Crawler)`.
- Cache every response; a rebuild never re-fetches.
- Raw HTML stays local (`data/raw/` is gitignored). We publish only derived factual data
  plus the URL manifest for provenance.
