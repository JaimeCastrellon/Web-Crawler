"""Pipeline orchestration: parse cache -> merge -> pre-game records -> splits -> CSVs.
Spec: docs/TASKS.md, Task 7.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ivydata.config import Config


def add_pregame_records(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Add games_before, wins_before, losses_before, ties_before, ivy_wins_before,
    ivy_losses_before — counting ONLY the team's earlier games in the same season."""
    raise NotImplementedError("Task 7")


def assign_splits(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Add the ``split`` column from config.splits."""
    raise NotImplementedError("Task 7")


def build(raw_dir: Path, out_dir: Path, config: Config) -> None:
    """Write games.csv, team_game_stats.csv and train/ test/ current/ subfolders.
    Deterministic: same raw cache -> byte-identical output."""
    raise NotImplementedError("Task 7")
