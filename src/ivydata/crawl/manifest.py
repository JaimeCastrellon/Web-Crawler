"""Provenance log of every fetched URL: data/manifest/urls.csv.

Columns (docs/DATA_DICTIONARY.md): url, school, season, kind, status, fetched_at, sha256,
season_slug. Spec: docs/TASKS.md, Task 2.
"""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

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
        self.path = Path(path)
        self._rows: dict[str, dict[str, str]] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != MANIFEST_COLUMNS:
                    raise ValueError(f"invalid manifest columns: {self.path}")
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(f"invalid manifest row: {self.path}")
                    self._rows[row["url"]] = row

    def record(
        self,
        result: FetchResult,
        school: str,
        season: int,
        kind: str,
        season_slug: str | None = None,
    ) -> None:
        """Insert or update the row for ``result.url``."""
        self._rows[result.url] = dict(
            zip(
                MANIFEST_COLUMNS,
                (
                    result.url,
                    school,
                    str(season),
                    kind,
                    str(result.status),
                    result.fetched_at,
                    result.sha256 or "",
                    season_slug or "",
                ),
                strict=True,
            )
        )

    def save(self) -> None:
        """Write CSV sorted by (school, season, kind, url)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(
            self._rows.values(),
            key=lambda row: (
                row["school"],
                int(row["season"]),
                row["kind"],
                row["url"],
            ),
        )
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=self.path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                writer = csv.DictWriter(stream, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
