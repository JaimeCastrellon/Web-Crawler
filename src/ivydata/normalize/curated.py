"""Load explicitly reviewed game facts bound to an unchanged cached PDF source."""

from __future__ import annotations

import json
import re
from datetime import date
from hashlib import sha1, sha256
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlsplit

from ivydata.config import Config
from ivydata.normalize.teams import canonical_team_id
from ivydata.parse.boxscore import GAME_FIELDS, TEAM_STAT_FIELDS, ParsedBoxscore

_ENTRY_FIELDS = {
    "url", "school", "season", "source_sha256", "source_fetched_at",
    "evidence_page", "evidence_region", "review_method", "game", "team_stats",
}  # fmt: skip
_TEXT_FIELDS = {"date", "home_raw", "away_raw", "stadium", "city"}


def load_reviewed_boxscores(path: Path, raw_dir: Path, config: Config) -> list[ParsedBoxscore]:
    """Read curated factual excerpts, not an automatic PDF parser or season aggregates.

    A reviewer records only this game's explicit values and a page/region pointer.
    Missing fields remain unknown. Every build verifies the complete PDF and its
    successful cache metadata before the excerpt can participate in normal merging.
    Unknown fields (including printed records), invalid identities and stale proof
    fail before any processed output is replaced.
    """
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"reviewed box scores must be a list: {path}")
    boxes = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            raise ValueError(f"invalid reviewed box-score fields: {path}")
        url = entry["url"]

        def reject(reason: str, source_url: object = url) -> NoReturn:
            raise ValueError(f"reviewed box score {source_url}: {reason}")

        if not isinstance(url, str):
            reject("invalid URL")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", parsed.hostname)
            or parsed.username
            or parsed.password
        ):
            reject("invalid HTTPS source URL")
        if (
            entry["review_method"] != "visual_cached_pdf"
            or type(entry["evidence_page"]) is not int
            or entry["evidence_page"] < 1
            or not isinstance(entry["evidence_region"], str)
            or not entry["evidence_region"].strip()
        ):
            reject("missing explicit review method or page/region evidence")
        if type(entry["season"]) is not int or entry["season"] not in config.splits.seasons():
            reject("season outside configured splits")
        school = config.school(entry["school"])
        body_path = raw_dir / parsed.hostname / f"{sha1(url.encode()).hexdigest()}.html"
        try:
            body = body_path.read_bytes()
            metadata = json.loads(body_path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            reject(f"PDF evidence unavailable ({type(exc).__name__})")
        if (
            not isinstance(metadata, dict)
            or not body.startswith(b"%PDF-")
            or sha256(body).hexdigest() != entry["source_sha256"]
            or metadata.get("sha256") != entry["source_sha256"]
            or metadata.get("status") != 200
            or metadata.get("url") != url
            or not entry["source_fetched_at"]
            or metadata.get("fetched_at") != entry["source_fetched_at"]
        ):
            reject("PDF evidence checksum/metadata mismatch")
        values = entry["game"]
        if not isinstance(values, dict) or set(values) - set(GAME_FIELDS):
            reject("invalid game fields; records and aggregates are forbidden")
        game = dict.fromkeys(GAME_FIELDS)
        game.update(values)
        for key, value in game.items():
            if value is None:
                continue
            if key in _TEXT_FIELDS:
                if not isinstance(value, str) or not value.strip():
                    reject(f"invalid game text: {key}")
            elif type(value) is not int or value < 0:
                reject(f"invalid nonnegative game integer: {key}")
        try:
            day = date.fromisoformat(game["date"] or "")
            pair = {
                side: canonical_team_id(game[f"{side}_raw"] or "", config.team_aliases)
                for side in ("away", "home")
            }
        except (ValueError, TypeError):
            reject("missing/invalid game date or team")
        if (
            day.isoformat() != game["date"]
            or day.year - (day.month <= 3) != entry["season"]
            or len(set(pair.values())) != 2
            or school.id not in pair.values()
            or any(game[f"{side}_pts"] is None for side in pair)
        ):
            reject("date/season/teams/finals do not identify a completed Ivy game")
        for side in pair:
            quarters = [game[f"{side}_q{i}"] for i in range(1, 5)]
            if all(q is not None for q in quarters) and (
                game[f"{side}_ot"] is not None or game["num_ot"] == 0
            ):
                if sum(quarters) + (game[f"{side}_ot"] or 0) != game[f"{side}_pts"]:
                    reject(f"quarter/final mismatch: {side}")
        identity = (url, game["date"], tuple(sorted(pair.values())))
        if identity in seen:
            reject("duplicate game excerpt")
        seen.add(identity)
        stats = entry["team_stats"]
        if not isinstance(stats, list) or len(stats) != 2:
            reject("exactly two team-stat rows are required")
        ordered = {}
        for row in stats:
            if not isinstance(row, dict) or set(row) - set(TEAM_STAT_FIELDS) - {
                "team_raw",
                "is_home",
            }:
                reject("invalid team-stat fields; records and aggregates are forbidden")
            if type(row.get("is_home")) is not bool:
                reject("team orientation must be explicit")
            if not isinstance(row.get("team_raw"), str) or not row["team_raw"].strip():
                reject("missing explicit team-stat name")
            side = "home" if row["is_home"] else "away"
            if (
                side in ordered
                or canonical_team_id(row.get("team_raw") or "", config.team_aliases) != pair[side]
            ):
                reject("team-stat identities do not match game teams")
            result = dict.fromkeys(TEAM_STAT_FIELDS)
            result.update(row)
            if not any(result[k] is not None for k in TEAM_STAT_FIELDS):
                reject("each team must have explicit game statistics")
            for key in TEAM_STAT_FIELDS:
                value = result[key]
                if value is not None and (
                    type(value) is not int or (value < 0 and "yds" not in key)
                ):
                    reject(f"invalid team-stat integer: {key}")
            for numerator, denominator in (
                ("pass_cmp", "pass_att"),
                ("pass_int", "pass_att"),
                ("fumbles_lost", "fumbles"),
                ("third_down_conv", "third_down_att"),
                ("fourth_down_conv", "fourth_down_att"),
            ):
                a, b = result[numerator], result[denominator]
                if a is not None and b is not None and a > b:
                    reject(f"invalid statistic bounds: {numerator}")
            ordered[side] = result
        boxes.append(ParsedBoxscore(url, game, [ordered["away"], ordered["home"]]))
    return boxes
