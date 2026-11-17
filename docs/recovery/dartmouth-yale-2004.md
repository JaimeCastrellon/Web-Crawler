# Recovered Yale–Dartmouth box score, 2004-10-09

Partial source-specific recovery for issue #9. Broader coverage gaps remain open.

- Game: Yale vs Dartmouth, 2004-10-09; Yale 24, Dartmouth 14.
- Source: [official Dartmouth statistics](https://dartmouthsports.com/news/2004/10/8/547065).
- Retrieval: HTTP 200 through Fetcher, with configured User-Agent, robots checks, per-host delays, and normal cache behavior. The cached body’s SHA-256 matches the committed source manifest.
- Content verified: game date, both teams, quarter/final scores, and the presence of full team statistics. Individual stat values still require the task 5 parser and validation.

The linked Yale copy returned HTTP 500 and Dartmouth’s current game center contains only the result. This archived article contains the full preformatted box score. Its article URL is dated October 8; the actual game date in the statistics is October 9, 2004.

Original unsuccessful URL: [https://yalebulldogs.com/sports/football/stats/2004/dartmouth/boxscore/10164](https://yalebulldogs.com/sports/football/stats/2004/dartmouth/boxscore/10164).

Provenance uses the existing manifest columns in
`data/manifest/recovered/dartmouth_yale_2004.csv`. The `school` column identifies the source
school, and `season` is 2004 regardless of the migration/publication date in the URL.
These supplement files are separate from the main crawl log so the original failures stay
visible and source-specific PRs do not overwrite one another.

The full body remains only in ignored `data/raw/`. No raw HTML, post-game W-L records, or
season-to-date aggregates are committed or extracted as model features. The current
coverage command reads only the main crawl manifest and direct schedule links; it does not
yet apply these alternate-source supplements. Do not label Yale 2004 fully covered until
fallback ingestion, box-score parsing, and validation are complete.
