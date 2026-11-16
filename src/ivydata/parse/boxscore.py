"""Box-score parser. Spec: docs/TASKS.md, Task 5.

Do NOT extract the W-L records printed in the page header — they are post-game
(AGENTS.md hard rule 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Keys of ParsedBoxscore.game
GAME_FIELDS = [
    "date", "home_raw", "away_raw", "stadium", "city", "attendance",
    "home_q1", "home_q2", "home_q3", "home_q4", "home_ot", "home_pts",
    "away_q1", "away_q2", "away_q3", "away_q4", "away_ot", "away_pts",
    "num_ot",
]  # fmt: skip

# Keys of each dict in ParsedBoxscore.team_stats (plus "team_raw", "is_home")
TEAM_STAT_FIELDS = [
    "first_downs",
    "rush_att", "rush_yds", "rush_td",
    "pass_cmp", "pass_att", "pass_yds", "pass_td", "pass_int",
    "total_plays", "total_yds",
    "fumbles", "fumbles_lost",
    "penalties", "penalty_yds",
    "third_down_conv", "third_down_att",
    "fourth_down_conv", "fourth_down_att",
    "sacks_allowed", "sack_yds_lost",
    "punts", "punt_yds",
    "time_of_possession_s",
]  # fmt: skip


@dataclass
class ParsedBoxscore:
    page_url: str
    game: dict  # GAME_FIELDS; missing values are None
    team_stats: list[dict]  # exactly two dicts: TEAM_STAT_FIELDS + team_raw + is_home
    warnings: list[str] = field(default_factory=list)


def parse_boxscore(html: str, page_url: str) -> ParsedBoxscore:
    raise NotImplementedError("Task 5")
