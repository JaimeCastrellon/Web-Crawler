"""Schedule-page parser (score-only rows). Spec: docs/TASKS.md, Task 4."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser, LexborNode

from ivydata.crawl.discover import find_boxscore_links
from ivydata.crawl.pages import GAME_SELECTOR, declared_schedule_season

BOX_PATTERN = r"/sports/football/stats/[^/]+/[^/]+/boxscore/\d+"
MONTHS = {
    name: index
    for index, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}


@dataclass
class ScheduleRow:
    school: str  # canonical id of the school whose page this is
    season: int
    date: str  # YYYY-MM-DD
    opponent_raw: str  # as printed; normalized later
    location: Literal["home", "away", "neutral"]
    venue: str | None
    result: Literal["W", "L", "T"] | None  # None if not yet played
    points: int | None
    opponent_points: int | None
    boxscore_url: str | None
    page_url: str


@dataclass
class ScheduleParse:
    rows: list[ScheduleRow]
    warnings: list[str] = field(default_factory=list)  # raw text of rows we couldn't parse


def _text(node: LexborNode | None) -> str:
    return " ".join(node.text(separator=" ", strip=True).split()) if node is not None else ""


def _game_date(game: LexborNode, season: int) -> str:
    time = game.css_first("time[datetime]")
    if time is not None:
        parsed = date.fromisoformat(time.attributes["datetime"][:10])
    else:
        text = _text(
            game.css_first(
                ".sidearm-schedule-game-opponent-date, "
                "[data-test-id='s-game-card-standard__header-game-date-details']"
            )
        )
        named = re.search(
            r"\b([A-Za-z]+)\.?\s*(\d{1,2})(?:st|nd|rd|th)?"
            r"(?:\s*,?\s*(\d{4}))?",
            text,
        )
        numeric = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", text)
        if named and named[1][:3].lower() in MONTHS:
            month, day = MONTHS[named[1][:3].lower()], int(named[2])
            year = int(named[3]) if named[3] else season + (month <= 3)
        elif numeric:
            month, day = int(numeric[1]), int(numeric[2])
            year = int(numeric[3]) if numeric[3] else season + (month <= 3)
        else:
            raise ValueError(f"unrecognized game date {text!r}")
        parsed = date(year, month, day)
    if parsed.year != season and not (parsed.year == season + 1 and parsed.month <= 3):
        raise ValueError(f"game date {parsed} does not belong to season {season}")
    return parsed.isoformat()


def _location(game: LexborNode, venue: str) -> Literal["home", "away", "neutral"]:
    classes = (game.attributes.get("class") or "").split()
    stamp = _text(game.css_first(".s-game-card__header__stamp .s-stamp__text")).lower()
    if (
        "sidearm-schedule-neutral-game" in classes
        or "s-game-card--neutral" in classes
        or stamp in {"neutral", "n"}
        or "fenway" in venue.lower()
    ):
        return "neutral"
    if "sidearm-schedule-away-game" in classes or stamp == "at":
        return "away"
    if "sidearm-schedule-home-game" in classes or stamp in {"vs", "vs."}:
        return "home"
    raise ValueError("unrecognized home/away/neutral designation")


def _scores(game: LexborNode) -> tuple[Literal["W", "L", "T"] | None, int | None, int | None]:
    text = _text(
        game.css_first(
            ".sidearm-schedule-game-result, "
            "[data-test-id='s-game-card-standard__header-game-team-score']"
        )
    )
    if not text or re.search(r"cancel|postpon|suspend|\bTBA\b|\bTBD\b", text, re.I):
        return None, None, None
    match = re.match(r"^(?:([WLT])\s*[,;:]?\s*)?(\d+)\s*[-–]\s*(\d+)(?=\s|\(|$)", text, re.I)
    if not match:
        raise ValueError(f"unrecognized game result {text!r}")
    points, allowed = int(match[2]), int(match[3])
    outcome: Literal["W", "L", "T"] = (
        match[1].upper()
        if match[1]
        else "W"
        if points > allowed
        else "L"
        if points < allowed
        else "T"
    )
    return outcome, points, allowed


def parse_schedule(html: str, school: str, season: int, page_url: str) -> ScheduleParse:
    """Parse legacy rows and current cards offline, retaining bad rows as raw-text warnings."""
    parsed = ScheduleParse([])
    tree = LexborHTMLParser(html)
    title = _text(tree.css_first("title"))
    declared = declared_schedule_season(html)
    if declared is not None and declared != season:
        parsed.warnings.append(
            f"{page_url}: page declares season {declared}, expected {season}; raw={title}"
        )
        return parsed
    games = tree.css(GAME_SELECTOR)
    if not games:
        parsed.warnings.append(f"{page_url}: no recognizable schedule rows; raw={_text(tree.body)}")
    for index, game in enumerate(games, 1):
        raw = _text(game)
        try:
            opponent = _text(
                game.css_first(
                    ".sidearm-schedule-game-opponent-name, "
                    "[data-test-id='s-game-card-standard__header-team-opponent-link']"
                )
            )
            if not opponent:
                raise ValueError("missing opponent name")
            game_date = _game_date(game, season)
            venue = _text(
                game.css_first(
                    ".sidearm-schedule-game-location, "
                    "[data-test-id='s-game-card-facility-and-location__details-standard']"
                )
            )
            location = _location(game, venue)
            outcome, points, opponent_points = _scores(game)
            links = find_boxscore_links(game.html, page_url, BOX_PATTERN)
            if not links:
                for anchor in game.css("a[href]"):
                    if re.search(r"box\s*score|final\s*stats", _text(anchor), re.I):
                        url = urljoin(page_url, anchor.attributes["href"])
                        if urlsplit(url).scheme in {"http", "https"}:
                            links.append(url)
            parsed.rows.append(
                ScheduleRow(
                    school,
                    season,
                    game_date,
                    opponent,
                    location,
                    venue or None,
                    outcome,
                    points,
                    opponent_points,
                    links[0] if links else None,
                    page_url,
                )
            )
            if outcome and points is not None and opponent_points is not None:
                expected = (
                    "W" if points > opponent_points else "L" if points < opponent_points else "T"
                )
                if expected != outcome:
                    parsed.warnings.append(
                        f"{page_url} row {index}: result contradicts score; raw={raw}"
                    )
            if len(set(links)) > 1:
                parsed.warnings.append(
                    f"{page_url} row {index}: multiple box-score URLs {links}; raw={raw}"
                )
        except ValueError as exc:
            parsed.warnings.append(f"{page_url} row {index}: {exc}; raw={raw}")
    return parsed
