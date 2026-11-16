"""Schedule-page parser (score-only rows). Spec: docs/TASKS.md, Task 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ScheduleRow:
    school: str  # canonical id of the school whose page this is
    season: int
    date: str  # YYYY-MM-DD
    opponent_raw: str  # as printed; normalized later
    location: Literal["home", "away", "neutral"]
    venue: str | None
    result: Literal["W", "L", "T"] | None  # None if not yet played
    points: int | None
    opponent_points: int | None
    boxscore_url: str | None
    page_url: str


@dataclass
class ScheduleParse:
    rows: list[ScheduleRow]
    warnings: list[str] = field(default_factory=list)  # raw text of rows we couldn't parse


def parse_schedule(html: str, school: str, season: int, page_url: str) -> ScheduleParse:
    raise NotImplementedError("Task 4")
