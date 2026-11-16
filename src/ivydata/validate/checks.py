"""Data-quality checks. Spec: docs/TASKS.md, Task 8."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass
class Issue:
    severity: Literal["error", "warning"]
    check: str  # e.g. "quarter_sum", "duplicate_game_id"
    game_id: str | None
    message: str
    url: str | None = None


def run_checks(games: pd.DataFrame, team_stats: pd.DataFrame) -> list[Issue]:
    raise NotImplementedError("Task 8")


def write_report(issues: list[Issue], games: pd.DataFrame, path: str) -> None:
    """Markdown report: counts per season/split, then issues grouped by check."""
    raise NotImplementedError("Task 8")
