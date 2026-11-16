# Sources and crawl etiquette

## Primary sources — official athletics sites (Sidearm Sports)

| school | base URL | verified example |
|---|---|---|
| Brown | https://brownbears.com | |
| Columbia | https://gocolumbialions.com | *unverified — confirm in task 1* |
| Cornell | https://cornellbigred.com | `/sports/football/stats/2004-05/yale-university/boxscore/4180` |
| Dartmouth | https://dartmouthsports.com | |
| Harvard | https://gocrimson.com | `/sports/football/stats/2025/yale-university/boxscore/32128` |
| Penn | https://pennathletics.com | `/sports/football/stats/2004/yale/boxscore/10596` |
| Princeton | https://goprincetontigers.com | |
| Yale | https://yalebulldogs.com | `/sports/football/stats/2024/dartmouth/boxscore/18407` |

Base URLs are configured in `config/sources.yaml`. Task 1 confirms each one and its
`robots.txt`.

## Known quirks
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
