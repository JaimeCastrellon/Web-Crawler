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
- Honor `robots.txt` and any `Crawl-delay`.
- One request at a time per host, ≥ 3 seconds apart.
- User-Agent: `ivy-football-data/0.1 (+https://github.com/JaimeCastrellon/Web-Crawler)`.
- Cache every response; a rebuild never re-fetches.
- Raw HTML stays local (`data/raw/` is gitignored). We publish only derived factual data
  plus the URL manifest for provenance.

## Saved row exports from the score proposal

The original PR #13 supplied 78 official schedule-page exports (Yale, Cornell, Penn)
and 208 Wikipedia team-season exports, captured on 2026-11-16. These are extracted
factual schedule rows, not raw HTML. They were acquired through an earlier browser
workflow and do not provide raw-response checksums. The integrated build labels
them as official_export/Wikipedia, hashes files and page payloads separately, and
keeps Wikipedia article URLs/revision ids and CC BY-SA 4.0 attribution. Future HTTP
collection uses the robots-aware Fetcher; old browser request scripts are not used.

Where available, parsed box scores and verified cached official schedules outrank
these exports. Source discrepancies are retained rather than resolved by widening
the date/team matching rules. The reviewed 2001 Penn–Dartmouth date correction is
conditional on corroborating official Penn input, and its raw disagreement stays
visible. Official Brown/Dartmouth 2021 schedules confirm two other disputed dates.
Merrimack's official Harvard 2025 box score fills a missing result so later Harvard
pre-game records can be computed without header records.
