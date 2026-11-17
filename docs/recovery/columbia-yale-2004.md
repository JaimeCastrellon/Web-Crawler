# Recovered Yale–Columbia box score, 2004-10-30

Partial source-specific recovery for issue #9. Broader coverage gaps remain open.

- Game: Yale vs Columbia, 2004-10-30; Yale 21, Columbia 14.
- Source: [official Columbia statistics](https://gocolumbialions.com/sports/2018/5/28/1361469).
- Retrieval: HTTP 200 through Fetcher, with configured User-Agent, robots checks, per-host delays, and normal cache behavior. The cached body’s SHA-256 matches the committed source manifest.
- Content verified: game date, both teams, quarter/final scores, and the presence of full team statistics. Individual stat values still require the task 5 parser and validation.

The linked Yale copy returned HTTP 500, while Columbia’s game-center page has no historical team-stat table. This separate archived Box Score page contains preformatted scoring and team-stat sections. The URL migration date is 2018; the game date inside the statistics is October 30, 2004.

Original unsuccessful URL: [https://yalebulldogs.com/sports/football/stats/2004/columbia/boxscore/10167](https://yalebulldogs.com/sports/football/stats/2004/columbia/boxscore/10167).

Provenance uses the existing manifest columns in
`data/manifest/recovered/columbia_yale_2004.csv`. The `school` column identifies the source
school, and `season` is 2004 regardless of the migration/publication date in the URL.
These supplement files are separate from the main crawl log so the original failures stay
visible and source-specific PRs do not overwrite one another.

The full body remains only in ignored `data/raw/`. No raw HTML, post-game W-L records, or
season-to-date aggregates are committed or extracted as model features. The current
coverage command reads only the main crawl manifest and direct schedule links; it does not
yet apply these alternate-source supplements. Do not label Yale 2004 fully covered until
fallback ingestion, box-score parsing, and validation are complete.
