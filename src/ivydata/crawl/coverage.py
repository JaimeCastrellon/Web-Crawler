"""Coverage audit: what exists for each (school, season). Spec: docs/TASKS.md, Task 3."""

from __future__ import annotations

import csv
import logging
import re
from datetime import date, timedelta
from hashlib import sha1, sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from urllib.parse import urlsplit

import pandas as pd
from selectolax.lexbor import LexborHTMLParser

from ivydata.config import REPO_ROOT, load_config
from ivydata.crawl.discover import ERROR_COLUMNS, find_boxscore_links
from ivydata.crawl.manifest import MANIFEST_COLUMNS
from ivydata.crawl.pages import (
    GAME_SELECTOR,
    challenge_provider,
    declared_schedule_season,
    has_boxscore_content,
)
from ivydata.normalize.teams import canonical_team_id
from ivydata.parse.boxscore import TEAM_STAT_FIELDS, parse_boxscore
from ivydata.parse.schedule import parse_schedule

Level = Literal["full", "partial", "score_only", "missing"]
REPORT_COLUMNS = [
    "school",
    "season",
    "schedule_url",
    "season_slug",
    "games_on_schedule",
    "boxscores_found",
    "level",
    "notes",
]
logger = logging.getLogger(__name__)


def coverage_level(games_on_schedule: int, boxscores_found: int, scores_found: int) -> Level:
    """full: every game has a box score; partial: some do; score_only: none do but the
    schedule shows results; missing: no usable schedule."""
    if min(games_on_schedule, boxscores_found, scores_found) < 0:
        raise ValueError("coverage counts cannot be negative")
    if max(boxscores_found, scores_found) > games_on_schedule:
        raise ValueError("coverage counts cannot exceed games on the schedule")
    if games_on_schedule and boxscores_found == games_on_schedule:
        return "full"
    if boxscores_found:
        return "partial"
    if scores_found:
        return "score_only"
    return "missing"


def _read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError(f"invalid CSV columns: {path}")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"invalid CSV row: {path}")
        return rows


def _cached_html(row: dict[str, str]) -> tuple[str | None, str]:
    url = row["url"]
    if row["status"] != "200":
        return None, f"HTTP {row['status']}: {url}"
    host = urlsplit(url).hostname or ""
    path = REPO_ROOT / "data/raw" / host / f"{sha1(url.encode()).hexdigest()}.html"
    try:
        content = path.read_bytes()
    except OSError as exc:
        return None, f"cached body unavailable ({type(exc).__name__}): {url}"
    if sha256(content).hexdigest() != row["sha256"]:
        return None, f"cache checksum mismatch: {url}"
    html = content.decode("utf-8", errors="replace")
    provider = challenge_provider(html)
    if provider:
        return None, f"{provider} bot challenge: {url}"
    return html, ""


def _schedule_counts(
    html: str,
    page_url: str,
    regex: str,
    boxes: dict[str, dict[str, str]],
    school: str,
    season: int,
    aliases: dict[str, str],
    recovered: dict[tuple, list[str]],
) -> tuple[int, int, int, list[str]]:
    games = [game for game in LexborHTMLParser(html).css(GAME_SELECTOR) if game.text(strip=True)]
    found = scores = 0
    notes: list[str] = []
    used: set[str] = set()
    checked: dict[str, tuple[bool, str]] = {}
    for game in games:
        result_nodes = game.css(
            ".sidearm-schedule-game-result, "
            "[data-test-id='s-game-card-standard__header-game-team-score']"
        )
        if any(re.search(r"\b\d+\s*[-–]\s*\d+\b", node.text()) for node in result_nodes):
            scores += 1
        available = False
        for url in find_boxscore_links(game.html, page_url, regex):
            if url not in checked:
                if url not in boxes:
                    checked[url] = False, f"box score not fetched: {url}"
                else:
                    box, reason = _cached_html(boxes[url])
                    usable = bool(box and has_boxscore_content(box))
                    checked[url] = (
                        usable,
                        reason or ("" if usable else f"unrecognized box-score content: {url}"),
                    )
            usable, reason = checked[url]
            if reason:
                notes.append(reason)
            if usable and url in used and not available:
                notes.append(f"box-score URL reused by multiple schedule games: {url}")
            if usable and url not in used and not available:
                used.add(url)
                available = True
        if not available and recovered:
            parsed = parse_schedule(game.html, school, season, page_url)
            if len(parsed.rows) == 1:
                row = parsed.rows[0]
                try:
                    pair = tuple(sorted((school, canonical_team_id(row.opponent_raw, aliases))))
                    day = date.fromisoformat(row.date)
                    matches = []
                    for offset in (-1, 0, 1):
                        matches.extend(
                            recovered.get(
                                (season, (day + timedelta(days=offset)).isoformat(), pair), []
                            )
                        )
                    for url in sorted(set(matches)):
                        if url not in used:
                            used.add(url)
                            available = True
                            notes.append(f"recovered box score matched by teams/date: {url}")
                            break
                except ValueError as exc:
                    notes.append(f"cannot match recovered box score ({exc}): {page_url}")
        found += available
    return len(games), found, scores, notes


def build_coverage_report() -> pd.DataFrame:
    """One row per (school, season) with the columns in docs/DATA_DICTIONARY.md,
    built from the manifest and the cached schedule pages."""
    config = load_config()
    manifests = [
        REPO_ROOT / "data/manifest/urls.csv",
        *sorted((REPO_ROOT / "data/manifest/recovered").glob("*.csv")),
    ]
    by_url = {}
    for path in manifests:
        for row in _read_csv(path, MANIFEST_COLUMNS):
            previous = by_url.get(row["url"])
            keys = ("kind", "season", "status", "sha256") + (
                ("school",) if row["kind"] == "schedule" else ()
            )
            if previous and any(previous[k] != row[k] for k in keys):
                raise ValueError(f"conflicting manifest entries: {row['url']}")
            by_url[row["url"]] = row
    manifest = list(by_url.values())
    errors = _read_csv(REPO_ROOT / "data/reports/crawl_errors.csv", ERROR_COLUMNS)
    boxes = {row["url"]: row for row in manifest if row["kind"] == "boxscore"}
    recovered = {}
    recovery_errors = []
    for url, row in sorted(boxes.items()):
        if row["status"] != "200":
            continue
        html, reason = _cached_html(row)
        if html is None:
            recovery_errors.append((row, reason))
            continue
        parsed = parse_boxscore(html, url)
        if not parsed.game["date"] or not any(
            t[k] is not None for t in parsed.team_stats for k in TEAM_STAT_FIELDS
        ):
            continue
        try:
            pair = tuple(
                sorted(
                    canonical_team_id(parsed.game[k] or "", config.team_aliases)
                    for k in ("home_raw", "away_raw")
                )
            )
            day = date.fromisoformat(parsed.game["date"])
            season = day.year - (day.month <= 3)
            if season != int(row["season"]) or pair[0] == pair[1]:
                recovery_errors.append(
                    (row, f"recovered game conflicts with manifest season/teams: {url}")
                )
                continue
            recovered.setdefault((season, day.isoformat(), pair), []).append(url)
        except ValueError as exc:
            recovery_errors.append((row, f"unusable recovery identity ({exc}): {url}"))
    rows = []
    for school in sorted(config.schools, key=lambda school: school.id):
        for season in sorted(config.splits.seasons()):
            schedules = [
                row
                for row in manifest
                if row["kind"] == "schedule"
                and row["school"] == school.id
                and int(row["season"]) == season
            ]
            slugs = school.season_slugs(season)
            schedules.sort(
                key=lambda row: (
                    slugs.index(row["season_slug"]) if row["season_slug"] in slugs else len(slugs),
                    row["url"],
                )
            )
            notes = [
                f"{row['error']}: {row['url']}"
                for row in errors
                if row["school"] == school.id and int(row["season"]) == season
            ]
            notes.extend(
                reason
                for entry, reason in recovery_errors
                if entry["school"] == school.id and int(entry["season"]) == season
            )
            chosen = None
            games = found = scores = 0
            for candidate in schedules:
                html, reason = _cached_html(candidate)
                if html is None:
                    notes.append(reason)
                    continue
                declared = declared_schedule_season(html)
                if declared is not None and declared != season:
                    notes.append(
                        f"page declares season {declared}, expected {season}: {candidate['url']}"
                    )
                    continue
                count, box_count, score_count, warnings = _schedule_counts(
                    html,
                    candidate["url"],
                    config.boxscore_regex,
                    boxes,
                    school.id,
                    season,
                    config.team_aliases,
                    recovered,
                )
                if not count:
                    notes.append(f"no recognizable schedule games: {candidate['url']}")
                    continue
                chosen = candidate
                games, found, scores = count, box_count, score_count
                notes.extend(warnings)
                break
            if not schedules:
                known = sorted(
                    {
                        url
                        for (year, _, pair), urls in recovered.items()
                        if year == season and school.id in pair
                        for url in urls
                    }
                )
                if known:
                    notes.append(
                        "no schedule manifest; recovered boxes available: " + ", ".join(known)
                    )
                elif not notes:
                    notes.append("not crawled (no schedule manifest entry)")
            if games and not found and not scores:
                notes.append("schedule present; no results or usable box scores yet")
            notes = sorted(set(notes))
            for note in notes:
                if "http" in note:
                    logger.warning("%s %s: %s", school.id, season, note)
            rows.append(
                {
                    "school": school.id,
                    "season": season,
                    "schedule_url": chosen["url"] if chosen else "",
                    "season_slug": chosen["season_slug"] if chosen else "",
                    "games_on_schedule": games,
                    "boxscores_found": found,
                    "level": coverage_level(games, found, scores),
                    "notes": " | ".join(notes),
                }
            )
    report = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    path = REPO_ROOT / "data/reports/coverage_report.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            report.to_csv(stream, index=False, lineterminator="\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return report
