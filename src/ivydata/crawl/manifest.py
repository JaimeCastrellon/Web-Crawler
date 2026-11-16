"""Provenance log of every fetched URL: data/manifest/urls.csv.

Columns (docs/DATA_DICTIONARY.md): url, school, season, kind, status, fetched_at, sha256,
season_slug. Spec: docs/TASKS.md, Task 2.
"""

from __future__ import annotations

from pathlib import Path

from ivydata.crawl.fetcher import FetchResult

MANIFEST_COLUMNS = [
    "url",
    "school",
    "season",
    "kind",  # schedule | boxscore | robots | news
    "status",
    "fetched_at",
    "sha256",
    "season_slug",
]


class Manifest:
    def __init__(self, path: Path) -> None:
        """Load an existing manifest from ``path`` (or start empty)."""
        raise NotImplementedError("Task 2")

    def record(
        self,
        result: FetchResult,
        school: str,
        season: int,
        kind: str,
        season_slug: str | None = None,
    ) -> None:
        """Insert or update the row for ``result.url``."""
        raise NotImplementedError("Task 2")

    def save(self) -> None:
        """Write CSV sorted by (school, season, kind, url)."""
        raise NotImplementedError("Task 2")
