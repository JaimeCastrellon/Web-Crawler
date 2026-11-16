"""Coverage audit: what exists for each (school, season). Spec: docs/TASKS.md, Task 3."""

from __future__ import annotations

from typing import Literal

import pandas as pd

Level = Literal["full", "partial", "score_only", "missing"]


def coverage_level(games_on_schedule: int, boxscores_found: int, scores_found: int) -> Level:
    """full: every game has a box score; partial: some do; score_only: none do but the
    schedule shows results; missing: no usable schedule."""
    raise NotImplementedError("Task 3")


def build_coverage_report() -> pd.DataFrame:
    """One row per (school, season) with the columns in docs/DATA_DICTIONARY.md,
    built from the manifest and the cached schedule pages."""
    raise NotImplementedError("Task 3")
