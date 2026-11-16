# Recovered Yale–Brown box score, 2004-11-06

Partial source-specific recovery for issue #9. Broader coverage gaps remain open.

- Game: Yale vs Brown, 2004-11-06; Yale 17, Brown 24.
- Source: [official Brown statistics](https://brownbears.com/sports/football/stats/2004/yale/boxscore/12944).
- Retrieval: HTTP 200 through Fetcher, with configured User-Agent, robots checks, per-host delays, and normal cache behavior. The cached body’s SHA-256 matches the committed source manifest.
- Content verified: game date, both teams, quarter/final scores, and the presence of full team statistics. Individual stat values still require the task 5 parser and validation.

The linked Yale copy returned HTTP 500. Brown’s modern box-score layout (boxscorePageId) contains the matching date, quarter scores, and full team-stat tables. It must be supported by the later box-score parser; it does not use the legacy article.box-score wrapper.

Original unsuccessful URL: [https://yalebulldogs.com/sports/football/stats/2004/brown/boxscore/10168](https://yalebulldogs.com/sports/football/stats/2004/brown/boxscore/10168).

Provenance uses the existing manifest columns in
`data/manifest/recovered/brown_yale_2004.csv`. The `school` column identifies the source
school, and `season` is 2004 regardless of the migration/publication date in the URL.
These supplement files are separate from the main crawl log so the original failures stay
visible and source-specific PRs do not overwrite one another.

The full body remains only in ignored `data/raw/`. No raw HTML, post-game W-L records, or
season-to-date aggregates are committed or extracted as model features. The current
coverage command reads only the main crawl manifest and direct schedule links; it does not
yet apply these alternate-source supplements. Do not label Yale 2004 fully covered until
fallback ingestion, box-score parsing, and validation are complete.
