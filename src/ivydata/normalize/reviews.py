"""Apply explicit date reviews only when checksum-verified schedule evidence agrees."""

from __future__ import annotations

import csv
import json
from datetime import date
from hashlib import sha1, sha256
from pathlib import Path
from urllib.parse import urlsplit

from ivydata.config import Config
from ivydata.normalize.teams import canonical_team_id
from ivydata.parse.boxscore import ParsedBoxscore
from ivydata.parse.schedule import parse_schedule

DATE_REVIEW_COLUMNS = [
    "url", "original_date", "date", "school", "evidence_url", "evidence_sha256",
    "evidence_fetched_at",
]  # fmt: skip


def load_box_date_reviews(path: Path) -> dict[str, dict[str, str]]:
    """Read the optional review ledger; malformed or duplicate entries fail explicitly."""
    if not path.exists():
        return {}
    reviews = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != DATE_REVIEW_COLUMNS:
            raise ValueError(f"invalid box-date review columns: {path}")
        for row in reader:
            if None in row or any(not value for value in row.values()) or row["url"] in reviews:
                raise ValueError(f"invalid/duplicate box-date review row: {path}")
            reviews[row["url"]] = row
    return reviews


def apply_box_date_review(
    box: ParsedBoxscore, review: dict[str, str], raw_dir: Path, config: Config
) -> str:
    """Correct one reviewed one-day typo, preserving the original as disagreement evidence.

    A matching official schedule must prove date, teams and finals. This does not
    infer corrections from nearby dataset rows or from article publication dates.
    """
    original, selected = (
        date.fromisoformat(review["original_date"]),
        date.fromisoformat(review["date"]),
    )
    if (
        box.page_url != review["url"]
        or box.game["date"] != review["original_date"]
        or original.isoformat() != review["original_date"]
        or selected.isoformat() != review["date"]
        or abs((selected - original).days) != 1
        or selected.year - (selected.month <= 3) != original.year - (original.month <= 3)
    ):
        raise ValueError(f"box-date review no longer matches source: {box.page_url}")
    school = config.school(review["school"])
    evidence_url = review["evidence_url"]
    parsed = urlsplit(evidence_url)
    if parsed.scheme != "https" or parsed.hostname != urlsplit(school.base_url).hostname:
        raise ValueError(f"box-date evidence is not the official school host: {evidence_url}")
    path = raw_dir / parsed.hostname / f"{sha1(evidence_url.encode()).hexdigest()}.html"
    content = path.read_bytes()
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if (
        sha256(content).hexdigest() != review["evidence_sha256"]
        or metadata.get("sha256") != review["evidence_sha256"]
        or metadata.get("url") != evidence_url
        or metadata.get("status") != 200
        or metadata.get("fetched_at") != review["evidence_fetched_at"]
    ):
        raise ValueError(f"box-date evidence checksum/metadata mismatch: {evidence_url}")
    teams = {
        side: canonical_team_id(box.game[f"{side}_raw"] or "", config.team_aliases)
        for side in ("home", "away")
    }
    if school.id not in teams.values() or len(set(teams.values())) != 2:
        raise ValueError(f"box-date evidence school does not play this game: {box.page_url}")
    side = "home" if teams["home"] == school.id else "away"
    other = "away" if side == "home" else "home"
    schedule = parse_schedule(
        content.decode("utf-8", errors="replace"),
        school.id,
        selected.year - (selected.month <= 3),
        evidence_url,
    )
    matching = [
        row
        for row in schedule.rows
        if row.date == selected.isoformat()
        and canonical_team_id(row.opponent_raw, config.team_aliases) == teams[other]
        and row.points is not None
        and row.opponent_points is not None
        and row.points == box.game[f"{side}_pts"]
        and row.opponent_points == box.game[f"{other}_pts"]
    ]
    if len(matching) != 1:
        raise ValueError(f"box-date evidence does not prove date/teams/finals: {evidence_url}")
    box._original_date = box.game["date"]
    box.game["date"] = selected.isoformat()
    return (
        f"reviewed box-score date {original} -> {selected}; "
        f"verified official schedule: {evidence_url}; original disagreement retained"
    )
