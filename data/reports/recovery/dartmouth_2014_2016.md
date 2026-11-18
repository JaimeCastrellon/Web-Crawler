# Dartmouth 2014–2016 source recovery

New requests are within the agreed 2006-onward scope. Previously collected older
rows and split ranges remain intact.

Accepted 15 checksum-verified Dartmouth boxes: 7 from 2014,
7 from 2015 and 1 from 2016. They add 14 previously
score-only games to the current branch; overlaps merge as additional provenance.
The snapshot now has 776 detailed-stat games, still 1,355 unique games.

Fetcher used the configured User-Agent, robots rules, cache and per-host delays.
After an unusable box response, remaining requests for that school/season were
deferred rather than repeatedly hitting a failing endpoint. The attempt inventory
distinguishes accepted boxes, discovery pages, rejected responses and unfetched
URLs; unfetched rows have no fabricated HTTP status/hash/time.

There are 13 persisted source diagnostics, including explicit
deferred URLs. They reach build/validation warnings through the source error CSV.
Only parsed, verified boxes enter the recovery manifest; no raw HTML is committed.
Missing statistics stay missing. Header W-L records are not features.

Validation: 0 errors, 207 warnings across the integrated snapshot.
Offline provenance tests check every recovered URL maps to one full-stat game.
All offline tests, format/lint, duplicate-id and whitespace checks are run before
publication. The broader 2006-onward coverage work remains issue #9.
