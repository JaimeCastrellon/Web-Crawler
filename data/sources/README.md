# Saved factual schedule exports

These four files were supplied by the original PR #13 on 2026-11-16. They contain
extracted schedule rows, not full HTML pages. Original acquisition used browser
exports; those exports do not provide raw-response SHA-256 hashes. They are a
separate provenance tier from responses downloaded and verified by Fetcher.
Future collection in this repository uses Fetcher; the legacy browser request
scripts are not part of the integrated workflow.

| file | source | pages / seasons |
|---|---|---|
| `ivy_official_yale.json` | Yale official schedule rows | 26 pages, 2000–2026 excluding 2020 |
| `ivy_official_cornell.json` | Cornell official schedule rows | 26 pages, split-year slugs |
| `ivy_official_penn.json` | Penn official schedule rows | 26 pages |
| `ivy_wikipedia_schedules.json` | eight schools' Wikipedia team-season articles | 208 pages, revision ids retained |

Wikipedia-derived entries are attributed to the linked articles and their
contributors, under CC BY-SA 4.0. Exact source URLs and revision ids are recorded in
`data/manifest/score_sources.csv`. That file records both the saved export's SHA-256
and a SHA-256 of the canonical JSON page payload; these are not raw HTML hashes.

`python -m ivydata build` automatically reads these documented filenames, combines
them with verified raw-cache sources and recovered box scores, and uses the shared
merge/pre-game/split/CSV pipeline. `python -m ivydata validate` checks the result.
The explicit `scores --official ... --wikipedia ...` compatibility command uses the
same pipeline. Rebuilding full box-score output also needs the matching local raw
cache; missing/corrupt successful cache entries stop publication rather than erasing
statistics. No network request is made during either build command.

Priority: parsed box scores, cached official schedules, official row exports, then
Wikipedia fallback rows. Only parsed source pages are cited as evidence. The
separate `boxscore_urls.txt` list is discovery metadata, not download evidence.
A missing overtime label stays unknown; positive reported OT counts are retained.
No printed header records are imported. All pre-game records are recomputed.

One reviewed correction aligns Dartmouth's exported 2001 Penn game from September
27 to September 29 only when the supplied official Penn copy corroborates it.
The original date remains in source-agreement checks and the correction is logged.
Other disagreements remain explicit in the validation report. Two official 2021
schedule checks and Merrimack's official Harvard 2025 box score are recorded in
recovery manifests. Raw exports themselves are not rewritten to hide disagreements.
