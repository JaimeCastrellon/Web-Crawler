"""Data-quality checks. Spec: docs/TASKS.md, Task 8."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import pandas as pd

from ivydata.build import GAME_COLUMNS, PREGAME_FIELDS, TEAM_COLUMNS, WARNING_COLUMNS
from ivydata.normalize.teams import IVY_TEAMS
from ivydata.parse.boxscore import TEAM_STAT_FIELDS


@dataclass
class Issue:
    severity: Literal["error", "warning"]
    check: str  # e.g. "quarter_sum", "duplicate_game_id"
    game_id: str | None
    message: str
    url: str | None = None


def _missing(value: object) -> bool:
    return value is None or pd.isna(value) or value == ""


def _number(value: object) -> int | None:
    if _missing(value) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return int(number) if math.isfinite(number) and number.is_integer() else None


def _boolean(value: object) -> bool | None:
    if _missing(value):
        return None
    return {"true": True, "false": False}.get(str(value).lower())


def _url(row: dict) -> str | None:
    value = row.get("source_urls")
    return str(value).split("|")[0] if not _missing(value) else None


def duplicate_game_ids(games: pd.DataFrame) -> list[Issue]:
    """Return errors for duplicated ids, independently of the rest of the schema."""
    if "game_id" not in games:
        return [Issue("error", "schema", None, "games.csv is missing game_id")]
    duplicate = games.loc[
        games["game_id"].notna() & games["game_id"].duplicated(keep=False), "game_id"
    ]
    return [
        Issue(
            "error",
            "duplicate_game_id",
            str(game_id),
            f"game_id occurs {int((games['game_id'] == game_id).sum())} times",
        )
        for game_id in sorted(set(duplicate))
    ]


def run_checks(games: pd.DataFrame, team_stats: pd.DataFrame) -> list[Issue]:
    """Check the present dataset offline; incomplete historical coverage is a warning."""
    issues = duplicate_game_ids(games)
    for name, frame, columns in [
        ("games", games, GAME_COLUMNS),
        ("team_game_stats", team_stats, TEAM_COLUMNS),
    ]:
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            issues.append(
                Issue("error", "schema", None, f"{name} is missing columns: {', '.join(missing)}")
            )
    if any(issue.check == "schema" for issue in issues):
        return _sorted(issues)
    game_rows = games.to_dict(orient="records")
    team_rows = team_stats.to_dict(orient="records")

    def add(
        check: str, row: dict, message: str, severity: Literal["error", "warning"] = "error"
    ) -> None:
        game_id = str(row["game_id"]) if not _missing(row.get("game_id")) else None
        issues.append(Issue(severity, check, game_id, message, _url(row)))

    for label, rows, fields in [
        (
            "game",
            game_rows,
            [
                "season",
                "attendance",
                "num_ot",
                *[
                    f"{s}_{f}"
                    for s in ("home", "away")
                    for f in ("pts", "q1", "q2", "q3", "q4", "ot")
                ],
            ],
        ),
        (
            "team",
            team_rows,
            ["season", "points", "points_allowed", "turnovers", *PREGAME_FIELDS, *TEAM_STAT_FIELDS],
        ),
    ]:
        for row in rows:
            identity = (
                ["game_id", "season", "date", "home_team", "away_team"]
                if label == "game"
                else ["game_id", "season", "date", "team", "opponent"]
            )
            if any(_missing(row[k]) for k in identity):
                add("missing_identity", row, f"{label} row has a missing game/team/date identity")
            for key in fields:
                value = row[key]
                number = _number(value)
                if not _missing(value) and (
                    number is None or (number < 0 and not key.endswith("_yds"))
                ):
                    add(
                        "impossible_value",
                        row,
                        f"{label} {row.get('team', '')}: {key}={value!r}; expected an integer"
                        + (" (negative yards allowed)" if key.endswith("_yds") else " >= 0"),
                    )
            for key in (
                ("neutral_site", "ivy_game", "sources_agree")
                if label == "game"
                else ("neutral_site", "is_home")
            ):
                if not _missing(row[key]) and _boolean(row[key]) is None:
                    add("impossible_value", row, f"{key}={row[key]!r}; expected true/false")
    game_rows = [
        r
        for r in game_rows
        if not any(_missing(r[k]) for k in ("game_id", "date", "season", "home_team", "away_team"))
    ]
    team_rows = [
        r
        for r in team_rows
        if not any(_missing(r[k]) for k in ("game_id", "date", "season", "team", "opponent"))
    ]
    for row in game_rows:
        try:
            day = date.fromisoformat(str(row["date"]))
            if day.isoformat() != row["date"] or day.year - (day.month <= 3) != _number(
                row["season"]
            ):
                raise ValueError("date/season mismatch")
        except ValueError:
            add("game_date", row, f"Invalid date/season: {row['date']!r}, {row['season']!r}")
        if _boolean(row["sources_agree"]) is False:
            add("source_disagreement", row, f"Sources disagree: {row['source_urls']}", "warning")
        if row["home_team"] == row["away_team"]:
            add("team_pair", row, "Home and away are the same team")
        for side in ("home", "away"):
            quarters = [_number(row[f"{side}_q{i}"]) for i in range(1, 5)]
            final, ot, num_ot = (
                _number(row[f"{side}_pts"]),
                _number(row[f"{side}_ot"]),
                _number(row["num_ot"]),
            )
            if (
                num_ot is not None
                and num_ot > 0
                and ot is None
                and any(q is not None for q in quarters)
            ):
                add(
                    "overtime",
                    row,
                    f"{side} OT points are missing for {num_ot} reported periods",
                    "warning",
                )
            if all(q is not None for q in quarters) and final is not None:
                if ot is not None or num_ot == 0:
                    total = sum(quarters) + (ot or 0)
                    if total != final:
                        add(
                            "quarter_sum",
                            row,
                            f"{side}: quarter/OT sum {total} differs from final {final}",
                        )
        expected_ivy = row["home_team"] in IVY_TEAMS and row["away_team"] in IVY_TEAMS
        if _boolean(row["ivy_game"]) != expected_ivy:
            add("ivy_flag", row, "ivy_game does not match the participating teams")

    duplicated = team_stats.duplicated(["game_id", "team"], keep=False)
    for game_id, group in team_stats[duplicated].groupby("game_id", sort=True):
        issues.append(
            Issue(
                "error",
                "duplicate_team_row",
                str(game_id),
                f"Duplicate team rows: {', '.join(sorted(set(group['team'].astype(str))))}",
            )
        )
    by_id = {row["game_id"]: row for row in game_rows}
    teams_by_id = defaultdict(list)
    for row in team_rows:
        teams_by_id[row["game_id"]].append(row)
    for row in game_rows:
        entries = teams_by_id[row["game_id"]]
        if len(entries) != 2 or {r["team"] for r in entries} != {
            row["home_team"],
            row["away_team"],
        }:
            add(
                "team_pair", row, f"Expected two team rows for home/away; found {len(entries)} rows"
            )
    for row in team_rows:
        game = by_id.get(row["game_id"])
        if game is None:
            add("orphan_team_row", row, f"No game row for team {row['team']}")
            continue
        side = "home" if row["team"] == game["home_team"] else "away"
        other = "away" if side == "home" else "home"
        expected = {
            "opponent": game[f"{other}_team"],
            "is_home": side == "home",
            "date": game["date"],
            "season": game["season"],
            "split": game["split"],
            "neutral_site": game["neutral_site"],
            "stats_level": game["stats_level"],
            "points": game[f"{side}_pts"],
            "points_allowed": game[f"{other}_pts"],
        }
        for key, value in expected.items():
            actual = row[key]
            if _missing(value) and _missing(actual):
                continue
            equal = (
                _boolean(value) == _boolean(actual)
                if key in ("is_home", "neutral_site")
                else _number(value) == _number(actual)
                if key in ("season", "points", "points_allowed")
                else value == actual
            )
            if not equal:
                add("team_context", game, f"{row['team']}.{key}={actual!r}, expected {value!r}")
        for numerator, denominator in [
            ("pass_cmp", "pass_att"),
            ("pass_int", "pass_att"),
            ("third_down_conv", "third_down_att"),
            ("fourth_down_conv", "fourth_down_att"),
            ("fumbles_lost", "fumbles"),
        ]:
            a, b = _number(row[numerator]), _number(row[denominator])
            if a is not None and b is not None and a > b:
                add(
                    "stat_bounds", game, f"{row['team']}: {numerator}={a} exceeds {denominator}={b}"
                )
        a, b, total = (_number(row[k]) for k in ("pass_int", "fumbles_lost", "turnovers"))
        if None not in (a, b, total) and a + b != total:
            add(
                "turnovers",
                game,
                f"{row['team']}: turnovers {total} differs from "
                f"interceptions + fumbles lost {a + b}",
            )
    for season in sorted(games["season"].dropna().unique(), key=str):
        rows = [g for g in game_rows if g["season"] == season]
        if rows and all(g["split"] == "current" for g in rows):
            continue
        for team in sorted(IVY_TEAMS):
            count = sum(
                g["home_team"] in IVY_TEAMS
                and g["away_team"] in IVY_TEAMS
                and team in (g["home_team"], g["away_team"])
                and _number(g["home_pts"]) is not None
                and _number(g["away_pts"]) is not None
                for g in rows
            )
            if count != 7:
                issues.append(
                    Issue(
                        "warning",
                        "ivy_game_count",
                        None,
                        f"{team}, season {season}: {count} completed Ivy games; "
                        "expected 7 in a full season",
                    )
                )
    return _sorted(issues)


def _sorted(issues: list[Issue]) -> list[Issue]:
    unique = {(i.severity, i.check, i.game_id, i.message, i.url): i for i in issues}
    return sorted(
        unique.values(),
        key=lambda i: (i.severity, i.check, i.game_id or "", i.message, i.url or ""),
    )


def read_build_warnings(path: Path) -> list[Issue]:
    """Carry saved source/parse/merge diagnostics into the validation report."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != WARNING_COLUMNS:
            raise ValueError(f"invalid build-warning columns: {path}")
        issues = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"invalid build-warning row: {path}")
            issues.append(
                Issue("warning", "build_warning", None, row["message"], row["source_url"] or None)
            )
    return _sorted(issues)


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def write_report(issues: list[Issue], games: pd.DataFrame, path: str) -> None:
    """Markdown report: counts per season/split, then issues grouped by check."""
    issues = _sorted(issues)
    lines = [
        "# Validation report",
        "",
        f"Game rows: {len(games)}. Errors: {sum(i.severity == 'error' for i in issues)}. "
        f"Warnings: {sum(i.severity == 'warning' for i in issues)}.",
        "",
        "This report checks the data currently present; "
        "it does not certify complete historical coverage.",
        "Ivy counts use completed games and expect seven in full seasons; "
        "current split seasons are excluded.",
        "",
        "## Games by season and split",
        "",
        "| Season | Split | Games | Full stats | Score only |",
        "|---|---|---:|---:|---:|",
    ]
    if {"season", "split", "stats_level"}.issubset(games.columns):
        for (season, split), group in games.groupby(["season", "split"], dropna=False, sort=True):
            lines.append(
                f"| {_escape(season)} | {_escape(split)} | {len(group)} | "
                f"{int((group['stats_level'] == 'full').sum())} | "
                f"{int((group['stats_level'] == 'score_only').sum())} |"
            )
    lines += ["", "## Issues", ""]
    if not issues:
        lines.append("No issues found in the supplied rows.")
    for check in sorted({i.check for i in issues}):
        lines += [f"### {_escape(check)}", ""]
        for issue in issues:
            if issue.check != check:
                continue
            label = f" — {_escape(issue.game_id)}" if issue.game_id else ""
            source = f" Source: {_escape(issue.url)}" if issue.url else ""
            lines.append(f"- **{issue.severity}**{label}: {_escape(issue.message)}{source}")
        lines.append("")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=target.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write("\n".join(lines).rstrip() + "\n")
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
