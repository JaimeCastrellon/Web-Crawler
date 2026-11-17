"""Merge box scores and schedule rows into one record per real game.
Spec: docs/TASKS.md, Task 6; game_id format: docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from itertools import groupby

from ivydata.normalize.teams import canonical_team_id, is_ivy
from ivydata.parse.boxscore import GAME_FIELDS, TEAM_STAT_FIELDS, ParsedBoxscore
from ivydata.parse.schedule import ScheduleRow

logger = logging.getLogger(__name__)


def _date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"expected ISO date YYYY-MM-DD, got {value!r}")
    return parsed


def make_game_id(date: str, home: str, away: str, neutral: bool) -> str:
    """``YYYYMMDD-away-at-home``, or ``YYYYMMDD-a-vs-b`` (alphabetical) at neutral sites."""
    stamp = _date(date).strftime("%Y%m%d")
    if home == away or any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", t) for t in (home, away)):
        raise ValueError(f"invalid canonical team pair: {home!r}, {away!r}")
    if neutral:
        a, b = sorted((home, away))
        return f"{stamp}-{a}-vs-{b}"
    return f"{stamp}-{away}-at-{home}"


@dataclass
class MergeResult:
    games: list[dict]  # columns of games.csv minus split / pre-game fields
    team_stats: list[dict]  # columns of team_game_stats.csv minus split / pre-game fields
    conflicts: list[str] = field(default_factory=list)  # human-readable, for the report


@dataclass
class _Copy:
    url: str
    kind: str
    date: str
    season: int
    home: str
    away: str
    neutral: bool | None
    game: dict
    stats: dict[str, dict]
    original_date: str | None = None
    aggregate_ot: bool = False

    @property
    def pair(self) -> tuple[str, str]:
        return tuple(sorted((self.home, self.away)))

    @property
    def rank(self) -> tuple:
        populated = sum(v is not None for v in self.game.values()) + sum(
            v is not None for row in self.stats.values() for v in row.values()
        )
        signature = json.dumps(self.__dict__, sort_keys=True, ensure_ascii=True)
        priority = {"boxscore": 0, "schedule": 1, "official_export": 2, "wikipedia": 3}
        return (priority[self.kind], -populated, self.url, signature)


def _note(result: MergeResult, message: str) -> None:
    logger.warning("%s", message)
    result.conflicts.append(message)


def _box_copy(box: ParsedBoxscore, aliases: dict[str, str], result: MergeResult) -> _Copy:
    game = {key: box.game.get(key) for key in GAME_FIELDS}
    day = _date(game["date"])
    home = canonical_team_id(game["home_raw"] or "", aliases)
    away = canonical_team_id(game["away_raw"] or "", aliases)
    make_game_id(day.isoformat(), home, away, False)
    stats = {}
    for row in box.team_stats:
        try:
            team = canonical_team_id(row.get("team_raw") or "", aliases)
        except (TypeError, ValueError) as exc:
            _note(result, f"{box.page_url}: unusable statistics team: {exc}; raw={row!r}")
            continue
        if team not in (home, away) or team in stats:
            _note(
                result, f"{box.page_url}: invalid/duplicate statistics team {row.get('team_raw')!r}"
            )
            continue
        stats[team] = {key: row.get(key) for key in TEAM_STAT_FIELDS}
    neutral = True if "fenway" in (game["stadium"] or "").lower() else None
    return _Copy(
        box.page_url,
        "boxscore",
        day.isoformat(),
        day.year - (day.month <= 3),
        home,
        away,
        neutral,
        game,
        stats,
        original_date=getattr(box, "_original_date", None),
        aggregate_ot=getattr(box, "_aggregate_ot", False),
    )


def _schedule_copy(row: ScheduleRow, aliases: dict[str, str]) -> _Copy:
    day = _date(row.date)
    school = canonical_team_id(row.school, aliases)
    opponent = canonical_team_id(row.opponent_raw, aliases)
    if row.location not in ("home", "away", "neutral"):
        raise ValueError(f"invalid location {row.location!r}")
    if row.season != day.year - (day.month <= 3):
        raise ValueError(f"date {row.date} conflicts with season {row.season}")
    home, away = (opponent, school) if row.location == "away" else (school, opponent)
    make_game_id(row.date, home, away, False)
    game = dict.fromkeys(GAME_FIELDS)
    game["date"] = row.date
    if row.points is not None and row.opponent_points is not None:
        game["num_ot"] = getattr(row, "num_ot", None)
    game["home_pts"] = row.opponent_points if row.location == "away" else row.points
    game["away_pts"] = row.points if row.location == "away" else row.opponent_points
    # A schedule venue can include city text; do not invent a stadium/city split.
    neutral = row.location == "neutral" or "fenway" in (row.venue or "").lower()
    return _Copy(
        row.page_url,
        "schedule" if getattr(row, "source_kind", "cached") == "cached" else row.source_kind,
        row.date,
        row.season,
        home,
        away,
        neutral,
        game,
        {},
        original_date=getattr(row, "original_date", None),
    )


def _value(copy: _Copy, key: str, home: str, away: str):
    if key.startswith(("home_", "away_")):
        target = home if key.startswith("home_") else away
        prefix = "home" if target == copy.home else "away"
        return copy.game.get(prefix + key[key.index("_") :])
    return copy.game.get(key)


def _merge_group(copies: list[_Copy], result: MergeResult) -> None:
    copies = sorted(copies, key=lambda c: c.rank)
    best = copies[0]
    neutral = any(c.neutral is True for c in copies)
    if neutral and best.kind != "boxscore":
        # Schedules do not designate a home team at neutral venues. Make this stable
        # even when each team's schedule lists itself first.
        away, home = best.pair
    else:
        home, away = best.home, best.away
    game_id = make_game_id(best.date, home, away, neutral)
    urls = sorted({c.url for c in copies})
    agrees = True

    def choose(key: str, observations: list[tuple[str, object]], core: bool = False):
        nonlocal agrees
        populated = [(url, value) for url, value in observations if value is not None]
        distinct = {json.dumps(v, sort_keys=True) for _, v in populated}
        if len(distinct) > 1:
            _note(
                result,
                f"{game_id}: conflicting {key}: "
                + "; ".join(f"{url}={value!r}" for url, value in populated),
            )
            if core:
                agrees = False
        return populated[0][1] if populated else None

    choose("date", [(c.url, c.original_date or c.date) for c in copies], True)
    choose("season", [(c.url, c.season) for c in copies], True)
    choose("neutral_site", [(c.url, c.neutral) for c in copies], True)
    if not neutral:
        choose("home_team", [(c.url, c.home) for c in copies], True)

    def observation(copy: _Copy, key: str):
        value = _value(copy, key, home, away)
        if key == "num_ot" and copy.aggregate_ot and value is not None:
            if any(
                not other.aggregate_ot
                and other.game.get("num_ot") is not None
                and other.game["num_ot"] >= value
                for other in copies
            ):
                return None  # a lower bound is not a contrary exact count
        return value

    game = {
        key: choose(
            key,
            [(c.url, observation(c, key)) for c in copies],
            core=key in ("home_pts", "away_pts"),
        )
        for key in GAME_FIELDS
        if key not in ("date", "home_raw", "away_raw")
    }
    stats_rows = []
    for team, opponent in ((away, home), (home, away)):
        stats = {
            key: choose(f"{team}.{key}", [(c.url, c.stats.get(team, {}).get(key)) for c in copies])
            for key in TEAM_STAT_FIELDS
        }
        stats_rows.append(stats | {"team": team, "opponent": opponent, "is_home": team == home})
    level = (
        "full"
        if any(row[k] is not None for row in stats_rows for k in TEAM_STAT_FIELDS)
        else "score_only"
    )
    game.update(
        game_id=game_id,
        season=best.season,
        date=best.date,
        home_team=home,
        away_team=away,
        neutral_site=neutral,
        ivy_game=is_ivy(home) and is_ivy(away),
        stats_level=level,
        sources_agree=agrees if len(urls) > 1 or not agrees else None,
        source_urls="|".join(urls),
    )
    result.games.append(game)
    for stats in stats_rows:
        side = "home" if stats["is_home"] else "away"
        other = "away" if stats["is_home"] else "home"
        result.team_stats.append(
            stats
            | {
                "game_id": game_id,
                "season": best.season,
                "date": best.date,
                "stats_level": level,
                "neutral_site": neutral,
                "points": game[f"{side}_pts"],
                "points_allowed": game[f"{other}_pts"],
            }
        )


def merge_games(
    boxscores: list[ParsedBoxscore],
    schedule_rows: list[ScheduleRow],
    aliases: dict[str, str],
) -> MergeResult:
    """Same team pair within ±1 day = same game. Box score beats schedule row.
    Two sources disagreeing on score/date -> ``sources_agree=False`` + a conflict entry."""
    result = MergeResult([], [])
    copies = []
    for box in boxscores:
        for warning in box.warnings:
            _note(result, warning)
        try:
            copies.append(_box_copy(box, aliases, result))
        except (TypeError, ValueError) as exc:
            _note(result, f"{box.page_url}: unusable box score: {exc}; raw={box.game!r}")
    for row in schedule_rows:
        try:
            copies.append(_schedule_copy(row, aliases))
        except (TypeError, ValueError) as exc:
            _note(result, f"{row.page_url}: unusable schedule row: {exc}; raw={row!r}")
    for _, pair_copies in groupby(
        sorted(copies, key=lambda c: (c.pair, c.date, c.rank)), key=lambda c: c.pair
    ):
        group: list[_Copy] = []
        previous_end = None
        for copy in pair_copies:
            if group and (_date(copy.date) - _date(group[0].date)).days > 1:
                _merge_group(group, result)
                previous_end = group[-1].date
                group = []
            if not group and previous_end and (_date(copy.date) - _date(previous_end)).days == 1:
                _note(
                    result,
                    f"{copy.url}: ambiguous date chain for {copy.pair}; "
                    f"kept separate rather than merging games more than one day apart",
                )
            group.append(copy)
        if group:
            _merge_group(group, result)
    result.games.sort(key=lambda r: (r["date"], r["game_id"]))
    result.team_stats.sort(key=lambda r: (r["date"], r["game_id"], r["team"]))
    result.conflicts = sorted(set(result.conflicts))
    return result
