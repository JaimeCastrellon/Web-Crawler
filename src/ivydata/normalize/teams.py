"""Canonical team ids. Spec: docs/TASKS.md, Task 6."""

from __future__ import annotations

IVY_TEAMS = frozenset(
    {"brown", "columbia", "cornell", "dartmouth", "harvard", "penn", "princeton", "yale"}
)


def canonical_team_id(raw_name: str, aliases: dict[str, str]) -> str:
    """Map a raw team name to a lowercase slug using ``Config.team_aliases``.

    Strip rankings ("#8 Harvard"), "at"/"vs." prefixes and trailing records. Unknown names
    are slugified ("Holy Cross" -> "holy-cross") and logged once.
    """
    raise NotImplementedError("Task 6")


def is_ivy(team_id: str) -> bool:
    return team_id in IVY_TEAMS
