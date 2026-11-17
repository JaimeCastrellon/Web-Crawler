# Processed snapshot: Yale 2004 and Brown 2004/2025

29 unique games and 58 team rows, built offline from the main URL manifest and
recovered-source manifests. Twenty-five games have team statistics; Yale's Dayton,
Colgate, Lehigh and Princeton games from 2004 remain score-only. Brown's twenty
2004/2025 games all have box scores. The overlapping Brown–Yale 2004 game is merged.
This is not the full 2000–2026 historical dataset.

The 19 games in 2004 are train data and Brown's ten 2025 games are test data under
the current split configuration. Current files are intentionally header-only.
Source URLs are retained per game. Pre-game records count only completed games
observed on earlier dates: Yale 2004 and Brown 2004/2025 schedules are complete,
but other opponents' full schedules are not. Their records are incomplete.

`python -m ivydata build` regenerates this snapshot from the matching local raw cache
without network access. Cache bodies are ignored by Git; manifests preserve their
checksums. Fresh downloads require updated provenance if response bodies change.
The validation report has 0 errors and 22 warnings: nine broken original Yale links
and thirteen incomplete opponent Ivy schedules. It does not certify full historical
coverage. The separate proposed 1,355-game score dataset in PR #13 is not integrated.
