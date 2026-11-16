"""Merge box scores and schedule rows into one record per real game.
Spec: docs/TASKS.md, Task 6; game_id format: docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ivydata.parse.boxscore import ParsedBoxscore
from ivydata.parse.schedule import ScheduleRow


def make_game_id(date: str, home: str, away: str, neutral: bool) -> str:
    """``YYYYMMDD-away-at-home``, or ``YYYYMMDD-a-vs-b`` (alphabetical) at neutral sites."""
    raise NotImplementedError("Task 6")


@dataclass
class MergeResult:
    games: list[dict]  # columns of games.csv minus split / pre-game fields
    team_stats: list[dict]  # columns of team_game_stats.csv minus split / pre-game fields
    conflicts: list[str] = field(default_factory=list)  # human-readable, for the report


def merge_games(
    boxscores: list[ParsedBoxscore],
    schedule_rows: list[ScheduleRow],
    aliases: dict[str, str],
) -> MergeResult:
    """Same team pair within ±1 day = same game. Box score beats schedule row.
    Two sources disagreeing on score/date -> ``sources_agree=False`` + a conflict entry."""
    raise NotImplementedError("Task 6")
